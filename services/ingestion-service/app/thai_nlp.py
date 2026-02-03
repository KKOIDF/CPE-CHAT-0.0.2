"""Thai NLP utilities using PythaiNLP for advanced text processing."""

from typing import List, Dict, Tuple
from collections import Counter

try:
    from pythainlp.tokenize import word_tokenize
    from pythainlp.corpus.common import thai_stopwords
    from pythainlp.tag import pos_tag
    from pythainlp.util import isthai
    _HAS_THAI = True
except Exception:
    _HAS_THAI = False
    def word_tokenize(x: str, **kwargs) -> List[str]: return x.split()
    def thai_stopwords() -> set: return set()
    def pos_tag(x: List[str], **kwargs) -> List[Tuple[str, str]]: return [(w, 'UNKN') for w in x]
    def isthai(x: str) -> bool: return False


def extract_keywords(text: str, top_k: int = 10, min_length: int = 2) -> List[str]:
    """Extract important Thai keywords from text using word frequency.
    
    Args:
        text: Input text
        top_k: Number of top keywords to return
        min_length: Minimum character length for keywords
    
    Returns:
        List of keyword strings
    """
    if not text or not _HAS_THAI:
        return []
    
    try:
        # Tokenize
        words = word_tokenize(text, engine='newmm', keep_whitespace=False)
        
        # Filter stopwords and short words
        stopwords = thai_stopwords()
        filtered = [
            w.strip() for w in words 
            if w.strip() 
            and len(w.strip()) >= min_length 
            and w.strip() not in stopwords
            and not w.isspace()
        ]
        
        # Count frequency
        freq = Counter(filtered)
        
        # Return top keywords
        return [word for word, _ in freq.most_common(top_k)]
    except Exception as e:
        print(f"Keyword extraction failed: {e}")
        return []


def filter_thai_nouns(text: str, top_k: int = 20) -> List[str]:
    """Extract Thai nouns using POS tagging.
    
    Args:
        text: Input text
        top_k: Maximum number of nouns to return
    
    Returns:
        List of noun strings
    """
    if not text or not _HAS_THAI:
        return []
    
    try:
        words = word_tokenize(text, engine='newmm')
        tagged = pos_tag(words, engine='perceptron', corpus='orchid_ud')
        
        # Extract nouns (NOUN, PROPN tags)
        nouns = [
            word for word, tag in tagged 
            if tag in ('NOUN', 'PROPN', 'NCMN', 'NPRP') 
            and len(word.strip()) >= 2
        ]
        
        # Return unique nouns with frequency ordering
        freq = Counter(nouns)
        return [word for word, _ in freq.most_common(top_k)]
    except Exception as e:
        print(f"POS tagging failed: {e}")
        return []


def is_mostly_thai(text: str, threshold: float = 0.5) -> bool:
    """Check if text is mostly Thai characters.
    
    Args:
        text: Input text
        threshold: Minimum ratio of Thai characters
    
    Returns:
        True if Thai ratio >= threshold
    """
    if not text:
        return False
    
    if not _HAS_THAI:
        # Fallback: check Unicode range
        thai_count = sum(1 for c in text if '\u0E00' <= c <= '\u0E7F')
        return thai_count / len(text) >= threshold
    
    try:
        return isthai(text, check_all=False)
    except Exception:
        thai_count = sum(1 for c in text if '\u0E00' <= c <= '\u0E7F')
        return thai_count / len(text) >= threshold


def word_count_thai(text: str) -> int:
    """Count words in Thai text using proper tokenization.
    
    Args:
        text: Input text
    
    Returns:
        Number of words
    """
    if not text or not _HAS_THAI:
        return len(text.split())
    
    try:
        words = word_tokenize(text, engine='newmm', keep_whitespace=False)
        return len([w for w in words if w.strip()])
    except Exception:
        return len(text.split())
