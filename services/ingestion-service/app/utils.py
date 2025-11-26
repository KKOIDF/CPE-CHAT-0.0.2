import re
import unicodedata
from typing import List, Dict, Optional
from .validation import script_ratios
from .config import THAI_WORD_TOKENIZER, THAI_SENT_TOKENIZER

_TH_CHR = r'\u0E00-\u0E7F'
_TH_PAIR = re.compile(rf'([{_TH_CHR}])\s+([{_TH_CHR}])')
_SENT_SPLIT = re.compile(r"(?<=[\.!?…\u0E2F\u0E5B\u0E46])\s+")
_BULLET_START = re.compile(r"^([\-\•\–\*]|\d+[\.)]|[ก-ฮ]\)|\([0-9]+\)|\([ก-ฮ]\))\s+")

try:
    from pythainlp.util import normalize as th_normalize
    from pythainlp.tokenize import word_tokenize, sent_tokenize
    from pythainlp.util import isthai
    from pythainlp.spell import correct as th_correct
    try:
        from pythainlp.corpus.common import thai_words as _thai_words
        _THAI_WORDS_SET = set(_thai_words())
    except Exception:
        _THAI_WORDS_SET = set()
    _HAS_THAI = True
except Exception:
    _HAS_THAI = False
    def th_normalize(x: str) -> str: return x
    def word_tokenize(x: str, **kwargs) -> List[str]: return x.split()
    def sent_tokenize(x: str, **kwargs) -> List[str]: return [x]
    def isthai(x: str) -> bool: return False
    def th_correct(x: str) -> str: return x
    _THAI_WORDS_SET = set()


def normalize_text(text: str, preserve_newlines: bool = True) -> str:
    if text is None:
        return ''
    t = text.replace('\r\n', '\n').replace('\r', '\n')
    t = unicodedata.normalize('NFC', t)
    t = t.replace('\u00A0', ' ')
    t = re.sub(r'[\u200B-\u200D\uFEFF]', '', t)
    t = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]', '', t)
    if preserve_newlines:
        lines = [re.sub(r'[ \t]+', ' ', ln).strip() for ln in t.split('\n')]
        t = '\n'.join(lines)
        t = re.sub(r'\n{3,}', '\n\n', t)
    else:
        t = re.sub(r'\s+', ' ', t).strip()
    return t


def tidy_thai_spacing(text: str) -> str:
    if not text: return text
    t = _TH_PAIR.sub(r'\1\2', text)
    return re.sub(r'[ \t]+', ' ', t)


def thai_postprocess(text: str) -> str:
    t = tidy_thai_spacing(text)
    if _HAS_THAI:
        try: t = th_normalize(t)
        except Exception: pass
    return t


def choose_ocr_lang_for_text(text: str, default: str = 'tha', latin_threshold: float = 0.15) -> str:
    th_r, la_r = script_ratios(text)
    if la_r >= latin_threshold:
        return 'tha+eng'
    return default


def clean_for_index(text: str) -> str:
    if text is None:
        return ''
    t = normalize_text(text, preserve_newlines=True)
    t = re.sub(r'([A-Za-z0-9])-\n([A-Za-z0-9])', r'\1\2', t)
    t = '\n'.join(ln.strip() for ln in t.split('\n'))
    t = re.sub(r'\n{3,}', '\n\n', t)
    t = thai_postprocess(t)
    return t.strip()


_URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
_NUM_TOKEN_RE = re.compile(r"^[\d,\.\-/:%]+$")
_NUM_SPAN_RE = re.compile(r"\d[\d,\.\-/:%]*")
_THAI_CHARS = re.compile(r"[\u0E00-\u0E7F]")


def _reduce_repeats(text: str) -> str:
    return re.sub(r"(.)\1{2,}", r"\1\1", text)


def clean_and_spell_correct_thai(
    text: str,
    custom_map: Optional[Dict[str, str]] = None,
    do_spell: bool = True,
) -> str:
    if not text:
        return ''
    t = normalize_text(text, preserve_newlines=False)
    # Mask URLs and numeric spans before tokenization
    url_map: Dict[str, str] = {}
    num_map: Dict[str, str] = {}
    def _mask(pattern: re.Pattern, base_text: str, tag: str, store: Dict[str, str]) -> str:
        idx = 0
        def repl(m: re.Match) -> str:
            nonlocal idx
            key = f"{tag}TOKEN{idx}"
            store[key] = m.group(0)
            idx += 1
            return key
        return pattern.sub(repl, base_text)
    t = _mask(_URL_RE, t, 'URL', url_map)
    t = _mask(_NUM_SPAN_RE, t, 'NUM', num_map)
    t = _reduce_repeats(t)
    if _HAS_THAI:
        try:
            t = th_normalize(t)
        except Exception:
            pass
    try:
        tokens = word_tokenize(t, engine='newmm', keep_whitespace=True)
    except Exception:
        tokens = list(t)
    out: List[str] = []
    for tok in tokens:
        if not tok:
            continue
        if tok.isspace() or tok in url_map or tok in num_map or _NUM_TOKEN_RE.fullmatch(tok):
            out.append(tok)
            continue
        if custom_map and tok in custom_map:
            out.append(custom_map[tok])
            continue
        # Skip if token is a known Thai word
        if tok in _THAI_WORDS_SET:
            out.append(tok)
            continue
        # Skip correction when token ends with a repeated char to avoid over-correction
        if do_spell and _HAS_THAI and _THAI_CHARS.search(tok) and not re.search(r"(.)\1$", tok):
            try:
                out.append(th_correct(tok))
            except Exception:
                out.append(tok)
        else:
            out.append(tok)
    cleaned = ''.join(out)
    # Restore masks
    # Restore numbers then URLs
    for k, v in num_map.items():
        cleaned = cleaned.replace(k, v)
    for k, v in url_map.items():
        cleaned = cleaned.replace(k, v)
    cleaned = tidy_thai_spacing(cleaned)
    return cleaned.strip()


def tokenize_thai_words(text: str, engine: str = None) -> List[str]:
    """Tokenize Thai text into words using PythaiNLP.
    
    Args:
        text: Text to tokenize
        engine: Word tokenizer engine (None = use config default)
                'newmm' - Fast and good for general text
                'attacut' - Best accuracy for modern Thai (default)
                'longest' - Good for formal/academic text
                'deepcut' - Deep learning based
    """
    if not text or not _HAS_THAI:
        return text.split()
    if engine is None:
        engine = THAI_WORD_TOKENIZER
    try:
        return word_tokenize(text, engine=engine, keep_whitespace=False)
    except Exception:
        # Fallback to newmm if engine fails
        try:
            return word_tokenize(text, engine='newmm', keep_whitespace=False)
        except Exception:
            return text.split()


def segment_sentences_thai(text: str, engine: str = None) -> List[str]:
    """Segment Thai text into sentences using PythaiNLP.
    
    Args:
        text: Text to segment
        engine: Sentence tokenizer engine (None = use config default)
                'crfcut' - Best for Thai academic text (default)
                'tltk' - Good for mixed Thai/English
    """
    if not text:
        return []
    if not _HAS_THAI:
        return [s.strip() for s in _SENT_SPLIT.split(text) if s.strip()]
    if engine is None:
        engine = THAI_SENT_TOKENIZER
    try:
        # Use PythaiNLP sentence tokenizer for better Thai handling
        sents = sent_tokenize(text, engine=engine)
        return [s.strip() for s in sents if s.strip()]
    except Exception:
        # Fallback to crfcut if engine fails
        try:
            sents = sent_tokenize(text, engine='crfcut')
            return [s.strip() for s in sents if s.strip()]
        except Exception:
            # Last resort: regex
            return [s.strip() for s in _SENT_SPLIT.split(text) if s.strip()]


def split_paragraphs_smart(text: str, use_thai_sent: bool = True) -> List[str]:
    if not text:
        return []
    t = text.strip()
    blocks = [b.strip() for b in re.split(r"\n\s*\n+", t) if b.strip()]
    out: List[str] = []
    for b in blocks:
        lines = [ln.rstrip() for ln in b.split('\n')]
        buf: List[str] = []
        for ln in lines:
            if _BULLET_START.search(ln):
                if buf:
                    out.append('\n'.join(buf).strip())
                    buf = []
                out.append(ln.strip())
            else:
                buf.append(ln)
        if buf:
            para = '\n'.join(buf).strip()
            if len(para) > 1200:
                # Use PythaiNLP sentence segmentation (default enabled)
                if use_thai_sent:
                    sents = segment_sentences_thai(para)
                else:
                    sents = [s.strip() for s in _SENT_SPLIT.split(para) if s.strip()]
                pack: List[str] = []
                cur = ''
                for s in sents:
                    if len(cur) + 1 + len(s) > 600:
                        if cur:
                            pack.append(cur.strip())
                        cur = s
                    else:
                        cur = (cur + ' ' + s).strip()
                if cur:
                    pack.append(cur.strip())
                out.extend(pack)
            else:
                out.append(para)
    out = [p for p in out if len(p.strip()) >= 2]
    return out
