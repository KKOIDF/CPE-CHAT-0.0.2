import re
import unicodedata
from typing import List
from .validation import script_ratios

_TH_CHR = r'\u0E00-\u0E7F'
_TH_PAIR = re.compile(rf'([{_TH_CHR}])\s+([{_TH_CHR}])')
_SENT_SPLIT = re.compile(r"(?<=[\.!?…\u0E2F\u0E5B\u0E46])\s+")
_BULLET_START = re.compile(r"^([\-\•\–\*]|\d+[\.)]|[ก-ฮ]\)|\([0-9]+\)|\([ก-ฮ]\))\s+")

try:
    from pythainlp.util import normalize as th_normalize
    _HAS_THAI = True
except Exception:
    _HAS_THAI = False
    def th_normalize(x: str) -> str: return x


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


def split_paragraphs_smart(text: str) -> List[str]:
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
