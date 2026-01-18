import os
import re
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

try:
    from neo4j import GraphDatabase  # type: ignore
except Exception:  # pragma: no cover
    GraphDatabase = None  # type: ignore


_THAI_TO_ARABIC = str.maketrans('๐๑๒๓๔๕๖๗๘๙', '0123456789')

COURSE_CODE_PATTERNS = [
    # Thai university common: 6 digits course codes (261101)
    re.compile(r"\b[0-9\u0E50-\u0E59]{6}\b"),
    # Hyphenated variant: 261-101
    re.compile(r"\b[0-9\u0E50-\u0E59]{3}[-–][0-9\u0E50-\u0E59]{3}\b"),
    # Spaced/dotted variant: 261 101, 261.101
    re.compile(r"\b[0-9\u0E50-\u0E59]{3}[ .\t]+[0-9\u0E50-\u0E59]{3}\b"),
    # English style: CPE101, ENG-101
    re.compile(r"\b[A-Z]{2,6}[-–]?[0-9]{3}\b"),
]


_STRICT_ALPHA_PREFIXES = {
    # Common prefixes observed in KMUTT curriculum documents
    'CPE', 'GEN', 'LNG', 'MTH', 'PHY', 'CHM', 'ENG', 'HUM', 'SSC',
}


_STRICT_ALPHA_CODE = re.compile(r"\b(?P<pfx>[A-Z]{2,6})\s*[-–]?\s*(?P<num>[0-9]{3})\b")

# Numeric 6-digit course codes (e.g., 261101) appear in many Thai curricula.
_STRICT_NUM6 = re.compile(r"\b(?P<num>[0-9]{6})\b")

# Credit pattern often near course entries: (3-0-6)
_CREDIT_PATT = re.compile(r"\(\s*\d+\s*[-–]\s*\d+\s*[-–]\s*\d+\s*\)")

_BAD_LINE_HINTS = [
    re.compile(r"\bpp\.?\b", re.IGNORECASE),
    re.compile(r"\bISSN\b", re.IGNORECASE),
    re.compile(r"\bISBN\b", re.IGNORECASE),
    re.compile(r"\bProceedings\b", re.IGNORECASE),
    re.compile(r"\bvol\.?\b", re.IGNORECASE),
]


def _extract_course_codes_for_schema(text: str) -> Set[str]:
    """Stricter course-code extraction for curriculum schema building.

    Goal: avoid false positives like page ranges (e.g., 251-254 -> 251254) from references.
    Strategy:
      - Prefer alpha+3digit codes (CPE100, GEN 121, etc). If prefix isn't in allowlist,
        only accept it when it appears at the beginning of a line.
      - Accept numeric 6-digit codes only on lines that look like course entries
        (credit pattern / 'หน่วยกิต' / 'credit').
    """
    if not text:
        return set()
    out: Set[str] = set()
    norm = text.translate(_THAI_TO_ARABIC)
    lines = [ln.strip() for ln in norm.splitlines() if ln.strip()]
    for ln in lines:
        # Skip likely bibliography/citation lines
        if any(p.search(ln) for p in _BAD_LINE_HINTS):
            continue

        # Alpha codes
        for m in _STRICT_ALPHA_CODE.finditer(ln.upper()):
            pfx = (m.group('pfx') or '').upper()
            num = m.group('num') or ''
            code = _norm_course_code(f"{pfx}{num}")
            if not code:
                continue
            if pfx in _STRICT_ALPHA_PREFIXES:
                out.add(code)
            else:
                # unknown prefix: accept only if it starts the line (often course listings)
                if m.start() <= 2:
                    out.add(code)

        # Numeric 6-digit codes (require course-entry context)
        if _CREDIT_PATT.search(ln) or ('หน่วยกิต' in ln) or ('CREDIT' in ln.upper()):
            for m in _STRICT_NUM6.finditer(ln):
                code = _norm_course_code(m.group('num') or '')
                if code:
                    out.add(code)

    return out


def _extract_course_codes(text: str) -> Set[str]:
    if not text:
        return set()
    norm = text.translate(_THAI_TO_ARABIC)
    out: Set[str] = set()
    for patt in COURSE_CODE_PATTERNS:
        for m in patt.findall(norm):
            code = m.replace('-', '').replace('–', '').replace(' ', '').replace('\t', '').replace('.', '')
            out.add(code)
    return out


def _neo4j_driver():
    if GraphDatabase is None:
        return None
    uri = os.getenv('NEO4J_URI')
    user = os.getenv('NEO4J_USER') or os.getenv('NEO4J_USERNAME')
    password = os.getenv('NEO4J_PASSWORD')
    if not (uri and user and password):
        return None
    return GraphDatabase.driver(uri, auth=(user, password))


def _ensure_schema(tx):
    # Constraints/indexes are idempotent on Neo4j 5+ with IF NOT EXISTS
    tx.run("CREATE CONSTRAINT chunk_doc_id IF NOT EXISTS FOR (c:Chunk) REQUIRE c.doc_id IS UNIQUE")
    tx.run("CREATE CONSTRAINT course_code IF NOT EXISTS FOR (c:Course) REQUIRE c.code IS UNIQUE")
    tx.run("CREATE CONSTRAINT program_key IF NOT EXISTS FOR (p:Program) REQUIRE p.program_key IS UNIQUE")
    tx.run("CREATE CONSTRAINT category_key IF NOT EXISTS FOR (c:Category) REQUIRE c.category_key IS UNIQUE")
    tx.run("CREATE CONSTRAINT semester_key IF NOT EXISTS FOR (s:SemesterPlan) REQUIRE s.semester_key IS UNIQUE")
    tx.run("CREATE CONSTRAINT document_key IF NOT EXISTS FOR (d:Document) REQUIRE d.doc_key IS UNIQUE")
    tx.run("CREATE INDEX chunk_domain IF NOT EXISTS FOR (c:Chunk) ON (c.domain)")
    tx.run("CREATE INDEX document_domain IF NOT EXISTS FOR (d:Document) ON (d.domain)")
    tx.run("CREATE INDEX course_domain IF NOT EXISTS FOR (c:Course) ON (c.domain)")

    # Vector index (Neo4j 5.11+). Best-effort: ignore if unsupported.
    # We use a fixed dim default for BGE-M3 (1024) but allow override by env.
    try:
        dim = int(os.getenv('NEO4J_VECTOR_DIM', '1024'))
    except Exception:
        dim = 1024
    try:
        tx.run(
            """
            CREATE VECTOR INDEX course_embedding IF NOT EXISTS
            FOR (c:Course) ON (c.embedding)
            OPTIONS {indexConfig: {`vector.dimensions`: $dim, `vector.similarity_function`: 'cosine'}}
            """,
            dim=dim,
        )
    except Exception:
        # Older Neo4j versions may not support vector indexes.
        pass


def _coerce_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _norm_course_code(code: str) -> str:
    if not code:
        return ''
    c = code.strip().upper()
    c = c.replace('–', '-').replace('—', '-')
    c = c.replace('-', '').replace(' ', '').replace('\t', '').replace('.', '')
    return c


_CATEGORY_HINTS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"หมวดวิชาศึกษาทั่วไป"), "หมวดวิชาศึกษาทั่วไป"),
    (re.compile(r"หมวดวิชาเฉพาะ"), "หมวดวิชาเฉพาะ"),
    (re.compile(r"หมวดวิชาแกน"), "หมวดวิชาแกน"),
    (re.compile(r"หมวดวิชาเลือก"), "หมวดวิชาเลือก"),
    (re.compile(r"หมวดวิชาบังคับ"), "หมวดวิชาบังคับ"),
    (re.compile(r"หมวดวิชาเสรี"), "หมวดวิชาเสรี"),
]


def _detect_category(text: str) -> Optional[str]:
    if not text:
        return None
    for patt, name in _CATEGORY_HINTS:
        if patt.search(text):
            return name
    return None


_SEMESTER_PATTERNS: List[re.Pattern] = [
    # ปี 1 เทอม 1
    re.compile(r"ปี\s*(?P<y>\d)\s*เทอม\s*(?P<t>\d)", re.IGNORECASE),
    # ปีที่ 1 เทอมที่ 1
    re.compile(r"ปีที่\s*(?P<y>\d)\s*เทอมที่\s*(?P<t>\d)", re.IGNORECASE),
    # ชั้นปีที่ 1 ภาคการศึกษาที่ 1
    re.compile(r"ชั้นปีที่\s*(?P<y>\d)\s*ภาคการศึกษาที่\s*(?P<t>\d)", re.IGNORECASE),
]


_SUMMER_PATTERNS: List[re.Pattern] = [
    re.compile(r"ปี\s*(?P<y>\d)\s*(เทอม\s*ฤดูร้อน|ภาคฤดูร้อน|ฤดูร้อน)", re.IGNORECASE),
    re.compile(r"ปีที่\s*(?P<y>\d)\s*(เทอมฤดูร้อน|ภาคฤดูร้อน|ฤดูร้อน)", re.IGNORECASE),
    re.compile(r"ชั้นปีที่\s*(?P<y>\d)\s*(ภาคฤดูร้อน|ฤดูร้อน)", re.IGNORECASE),
]


def _detect_semester_plan(text: str) -> Optional[Tuple[int, int, str]]:
    if not text:
        return None
    for patt in _SEMESTER_PATTERNS:
        m = patt.search(text)
        if not m:
            continue
        try:
            y = int(m.group('y'))
            t = int(m.group('t'))
        except Exception:
            continue
        if y <= 0 or t <= 0:
            continue
        label = f"ปี {y} เทอม {t}"
        return y, t, label
    for patt in _SUMMER_PATTERNS:
        m = patt.search(text)
        if not m:
            continue
        try:
            y = int(m.group('y'))
        except Exception:
            continue
        if y <= 0:
            continue
        # represent summer as term=3
        return y, 3, f"ปี {y} ฤดูร้อน"
    return None


def _semester_key(domain: str, year: int, term: int) -> str:
    # term: 1/2 regular, 3 = summer
    if term == 3:
        return f"{domain}|Y{year}S".lower()
    return f"{domain}|Y{year}T{term}".lower()


def _parse_credit_breakdown(line: str) -> Optional[Tuple[int, int, int]]:
    if not line:
        return None
    m = _CREDIT_PATT.search(line)
    if not m:
        return None
    raw = m.group(0)
    nums = re.findall(r"\d+", raw)
    if len(nums) != 3:
        return None
    try:
        lec = int(nums[0]); lab = int(nums[1]); self_ = int(nums[2])
    except Exception:
        return None
    return lec, lab, self_


def _extract_title_after_code(line: str, code: str) -> Optional[str]:
    if not line or not code:
        return None
    # Find the first occurrence of the code (dense match)
    dense = _dense_norm(line)
    pos = dense.find(code)
    if pos < 0:
        return None

    # Fallback: use regex search in original line for better slicing
    patt = re.compile(re.escape(code[:3]) + r"\s*[-–]?\s*" + re.escape(code[3:]) + r"\b", re.IGNORECASE)
    m = patt.search(line)
    if not m:
        return None
    tail = line[m.end():].strip()
    if not tail:
        return None

    # Remove credit pattern and any trailing artifacts
    tail = _CREDIT_PATT.sub('', tail).strip()
    # Trim very long tails
    if len(tail) > 160:
        tail = tail[:160]

    # Remove leading separators
    tail = tail.lstrip(':-–—|')
    tail = tail.strip()
    if not tail:
        return None
    return tail


def _parse_curriculum_structure(text: str, domain: str) -> Tuple[Dict[str, Set[str]], Dict[str, Set[str]], Dict[str, Dict[str, Any]], Dict[str, str]]:
    """Parse curriculum structure (best-effort) from raw chunk text.

    Returns:
      - category_links: category_name -> set(course_code)
      - semester_links: semester_key -> set(course_code)
      - course_meta: course_code -> {title?, credits_total?, credit_lec?, credit_lab?, credit_self?}
      - semester_labels: semester_key -> label
    """
    category_links: Dict[str, Set[str]] = {}
    semester_links: Dict[str, Set[str]] = {}
    course_meta: Dict[str, Dict[str, Any]] = {}
    semester_labels: Dict[str, str] = {}

    current_category: Optional[str] = None
    current_sem_key: Optional[str] = None

    norm = text.translate(_THAI_TO_ARABIC) if text else ''
    for raw_ln in (norm or '').splitlines():
        ln = raw_ln.strip()
        if not ln:
            continue

        # Update context from headings
        cat = _detect_category(ln)
        if cat:
            current_category = cat

        sem = _detect_semester_plan(ln)
        if sem:
            y, t, label = sem
            current_sem_key = _semester_key(domain, y, t)
            semester_labels[current_sem_key] = label

        # Extract codes from this line
        codes = sorted({_norm_course_code(x) for x in _extract_course_codes_for_schema(ln) if x})
        codes = [c for c in codes if c]
        if not codes:
            continue

        # Link to current context
        if current_category:
            category_links.setdefault(current_category, set()).update(codes)
        if current_sem_key:
            semester_links.setdefault(current_sem_key, set()).update(codes)

        # Extract title + credit for each code (only from plausible course-entry lines)
        credit = _parse_credit_breakdown(ln)
        for code in codes:
            meta = course_meta.setdefault(code, {})
            title = _extract_title_after_code(ln, code)
            if title:
                # Keep the longer/more informative title
                prev = str(meta.get('title') or '')
                if len(title) > len(prev):
                    meta['title'] = title
            if credit:
                lec, lab, self_ = credit
                meta['credit_lec'] = lec
                meta['credit_lab'] = lab
                meta['credit_self'] = self_
                meta['credits_total'] = lec

    return category_links, semester_links, course_meta, semester_labels


def _dense_norm(text: str) -> str:
    if not text:
        return ''
    norm = text.translate(_THAI_TO_ARABIC).upper()
    return re.sub(r'[^A-Z0-9]', '', norm)


def _primary_code_for_chunk(text: str, codes: List[str]) -> Optional[str]:
    if not text or not codes:
        return None
    dense = _dense_norm(text)
    best_code = None
    best_pos = None
    for c in codes:
        if not c:
            continue
        pos = dense.find(c)
        if pos < 0:
            continue
        if best_pos is None or pos < best_pos:
            best_pos = pos
            best_code = c
    return best_code


def _looks_like_table(text: str, codes_count: int) -> bool:
    if not text:
        return False
    if text.count('|') >= 6:
        return True
    if codes_count >= 18 and (len(text) / max(1, codes_count)) < 60:
        return True
    # Many short lines can be table-like
    lines = [ln for ln in (text or '').splitlines() if ln.strip()]
    if len(lines) >= 18:
        short = sum(1 for ln in lines if len(ln.strip()) <= 20)
        if short / max(1, len(lines)) > 0.55:
            return True
    return False


def upsert_program_courses_to_neo4j_from_chunks(
    chunks: Iterable[Dict[str, Any]],
    domain: Optional[str] = None,
    program_name: Optional[str] = None,
    max_codes_per_chunk: int = 3,
    min_chunk_chars: int = 80,
    max_chunks_per_course: int = 4,
    primary_only_when_many: bool = True,
    primary_code_window: int = 140,
    course_limit: int = 0,
) -> int:
    """Build a lightweight curriculum schema in Neo4j from chunk text.

    Creates:
      (:Program)-[:HAS_COURSE]->(:Course)
      (:Course) has:
        - code (unique)
        - description (aggregated from chunk text mentioning that code)
        - embedding (BGE-M3 via app.chroma_client._embed_texts)

    Notes:
      - This is heuristic-based because the source is chunked PDF text.
      - Category/SemesterPlan/Outcome relations can be added later when structured data is available.
      - If Neo4j env vars aren't configured, this becomes a no-op.
    """
    drv = _neo4j_driver()
    if not drv:
        return 0

    neo4j_db = os.getenv('NEO4J_DATABASE')
    dom = (domain or os.getenv('CPE_DOMAIN', 'curriculum')).strip().lower() or 'curriculum'
    prog_name = (program_name or os.getenv('CPE_PROGRAM_NAME') or dom).strip() or dom

    # Build per-course text candidates from chunks
    # Heuristic:
    # - For course descriptions: assign chunk to a single "primary" code (earliest occurrence)
    #   to avoid exploding when a chunk contains prereq lists or tables.
    # - For structure (category/semester): it's okay to keep many codes.
    course_texts: Dict[str, List[Tuple[int, str]]] = {}
    category_links: Dict[str, Set[str]] = {}  # category_name -> set(course_code)
    semester_links: Dict[str, Set[str]] = {}  # semester_key -> set(course_code)
    semester_labels: Dict[str, str] = {}
    course_meta: Dict[str, Dict[str, Any]] = {}
    for c in chunks:
        text = str(c.get('text') or '')
        if not text or len(text.strip()) < min_chunk_chars:
            continue

        # Parse structure line-by-line for better semester/category coverage
        cl, sl, cm, slabels = _parse_curriculum_structure(text, dom)
        for k, v in cl.items():
            category_links.setdefault(k, set()).update(v)
        for k, v in sl.items():
            semester_links.setdefault(k, set()).update(v)
        semester_labels.update(slabels)
        for code, meta in cm.items():
            course_meta.setdefault(code, {}).update({k: v for k, v in meta.items() if v is not None})

        # For course description aggregation, we use strict codes from whole chunk.
        codes = sorted({_norm_course_code(x) for x in _extract_course_codes_for_schema(text) if x})
        codes = [x for x in codes if x]
        if not codes:
            continue

        # Course description aggregation: pick primary code and keep only that mapping
        if _looks_like_table(text, len(codes)):
            continue

        primary = _primary_code_for_chunk(text, codes)
        if not primary:
            continue

        if max_codes_per_chunk > 0 and len(codes) > max_codes_per_chunk:
            if not primary_only_when_many:
                continue
            # require primary code to appear early if we are tolerating many codes
            dense = _dense_norm(text)
            pos = dense.find(primary)
            if pos < 0 or pos > max(10, int(primary_code_window)):
                continue

        chunk_id = _coerce_int(c.get('chunk_id') or 0, 0)
        course_texts.setdefault(primary, []).append((chunk_id, text))

    if not course_texts:
        try:
            drv.close()
        except Exception:
            pass
        return 0

    # Aggregate descriptions (stable order)
    course_rows: List[Dict[str, Any]] = []
    for code, items in course_texts.items():
        items.sort(key=lambda x: x[0])
        selected = [t for (_cid, t) in items[: max(1, int(max_chunks_per_course))]]
        desc = '\n\n'.join([s.strip() for s in selected if s and s.strip()])
        # prevent pathological sizes
        if len(desc) > 12000:
            desc = desc[:12000]
        row: Dict[str, Any] = {'code': code, 'description': desc}
        meta = course_meta.get(code) or {}
        if meta.get('title'):
            row['title'] = meta.get('title')
        if meta.get('credits_total') is not None:
            row['credits_total'] = meta.get('credits_total')
        if meta.get('credit_lec') is not None:
            row['credit_lec'] = meta.get('credit_lec')
        if meta.get('credit_lab') is not None:
            row['credit_lab'] = meta.get('credit_lab')
        if meta.get('credit_self') is not None:
            row['credit_self'] = meta.get('credit_self')
        course_rows.append(row)

    # Stable order for batching + optional limit for safety
    course_rows.sort(key=lambda r: r.get('code') or '')
    if course_limit and int(course_limit) > 0:
        course_rows = course_rows[: int(course_limit)]

    # Embed descriptions using the ingestion-service embedder (BGE-M3 by default)
    # We keep it best-effort: if embedding fails, we skip writing embeddings.
    embeddings: List[List[float]] = []
    try:
        from .chroma_client import _embed_texts  # type: ignore
        from .utils import clean_and_spell_correct_thai  # type: ignore

        # Improve embedding text by prepending code/title/credits when available
        descs = []
        for r in course_rows:
            header_bits = [r.get('code')]
            if r.get('title'):
                header_bits.append(str(r.get('title')))
            if r.get('credits_total') is not None:
                header_bits.append(f"credits {r.get('credits_total')}")
            header = ' - '.join([b for b in header_bits if b])
            body = str(r.get('description') or '')
            combo = (header + "\n" + body).strip() if header else body
            descs.append(combo)
        try:
            cleaned = [clean_and_spell_correct_thai(d) for d in descs]
        except Exception:
            cleaned = descs
        embeddings = _embed_texts(cleaned, is_query=False)
    except Exception as e:
        print(f"[Neo4j] WARN: embedding failed; will upsert courses without embeddings: {e}")
        embeddings = []

    if embeddings and len(embeddings) == len(course_rows):
        dim = len(embeddings[0]) if embeddings and embeddings[0] else 0
        for i, row in enumerate(course_rows):
            row['embedding'] = embeddings[i]
        print(f"[Neo4j] Prepared {len(course_rows)} course embeddings (dim={dim}).")
    else:
        print(f"[Neo4j] Prepared {len(course_rows)} courses (no embeddings).")

    program_key = f"{dom}|{prog_name}".lower()

    def _apply_schema(tx):
        _ensure_schema(tx)

    def _upsert_courses(tx, batch_rows):
        tx.run(
            """
            MERGE (p:Program {program_key: $program_key})
            SET p.name = $program_name,
                p.domain = $domain
            WITH p
            UNWIND $rows AS r
            MERGE (c:Course {code: r.code})
            SET c.domain = $domain,
                c.description = r.description
            FOREACH (_ IN CASE WHEN r.title IS NULL THEN [] ELSE [1] END |
                SET c.title = r.title
            )
            FOREACH (_ IN CASE WHEN r.credits_total IS NULL THEN [] ELSE [1] END |
                SET c.credits_total = r.credits_total
            )
            FOREACH (_ IN CASE WHEN r.credit_lec IS NULL THEN [] ELSE [1] END |
                SET c.credit_lec = r.credit_lec
            )
            FOREACH (_ IN CASE WHEN r.credit_lab IS NULL THEN [] ELSE [1] END |
                SET c.credit_lab = r.credit_lab
            )
            FOREACH (_ IN CASE WHEN r.credit_self IS NULL THEN [] ELSE [1] END |
                SET c.credit_self = r.credit_self
            )
            FOREACH (_ IN CASE WHEN r.embedding IS NULL THEN [] ELSE [1] END |
                SET c.embedding = r.embedding
            )
            MERGE (p)-[:HAS_COURSE]->(c)
            """,
            program_key=program_key,
            program_name=prog_name,
            domain=dom,
            rows=batch_rows,
        )

    def _upsert_categories(tx, rows):
        tx.run(
            """
            MERGE (p:Program {program_key: $program_key})
            SET p.name = $program_name,
                p.domain = $domain
            WITH p
            UNWIND $rows AS r
            MERGE (cat:Category {category_key: r.category_key})
            SET cat.name = r.name,
                cat.domain = $domain
            MERGE (p)-[:HAS_CATEGORY]->(cat)
            WITH cat, r
            UNWIND r.codes AS code
            MERGE (c:Course {code: code})
            SET c.domain = $domain
            MERGE (cat)-[:HAS_COURSE]->(c)
            """,
            program_key=program_key,
            program_name=prog_name,
            domain=dom,
            rows=rows,
        )

    def _upsert_semesters(tx, rows):
        tx.run(
            """
            MERGE (p:Program {program_key: $program_key})
            SET p.name = $program_name,
                p.domain = $domain
            WITH p
            UNWIND $rows AS r
            MERGE (s:SemesterPlan {semester_key: r.semester_key})
            SET s.label = r.label,
                s.domain = $domain
            MERGE (p)-[:HAS_SEMESTER_PLAN]->(s)
            WITH s, r
            UNWIND r.codes AS code
            MERGE (c:Course {code: code})
            SET c.domain = $domain
            MERGE (s)-[:HAS_COURSE]->(c)
            """,
            program_key=program_key,
            program_name=prog_name,
            domain=dom,
            rows=rows,
        )

    # Write to Neo4j
    with drv.session(database=neo4j_db) as session:
        session.execute_write(_apply_schema)
        batch_size = int(os.getenv('NEO4J_UPSERT_BATCH', '200'))
        total = len(course_rows)
        sent = 0
        for i in range(0, total, batch_size):
            sub = course_rows[i:i + batch_size]
            session.execute_write(_upsert_courses, sub)
            sent += len(sub)
            if sent % (batch_size * 5) == 0 or sent == total:
                print(f"[Neo4j] Upserted {sent}/{total} courses...")

        # Categories and semesters are much smaller; batch separately
        if category_links:
            cat_rows = []
            for name, codes in category_links.items():
                cat_rows.append({
                    'name': name,
                    'category_key': f"{program_key}|{name}".lower(),
                    'codes': sorted(codes),
                })
            for i in range(0, len(cat_rows), batch_size):
                session.execute_write(_upsert_categories, cat_rows[i:i + batch_size])
            print(f"[Neo4j] Upserted {len(cat_rows)} categories...")

        if semester_links:
            sem_rows = []
            for sem_key, codes in semester_links.items():
                sem_rows.append({
                    'semester_key': sem_key,
                    'label': semester_labels.get(sem_key) or sem_key,
                    'codes': sorted(codes),
                })
            for i in range(0, len(sem_rows), batch_size):
                session.execute_write(_upsert_semesters, sem_rows[i:i + batch_size])
            print(f"[Neo4j] Upserted {len(sem_rows)} semester plans...")

    try:
        drv.close()
    except Exception:
        pass

    return len(course_rows)


def reset_program_schema_in_neo4j(domain: str, program_name: Optional[str] = None) -> int:
    """Remove Program/Category/SemesterPlan subgraph for a domain/program_key.

    Leaves Course nodes intact (they may be shared), but removes HAS_* relationships
    from the Program so a rebuild can re-link only valid courses.
    """
    drv = _neo4j_driver()
    if not drv:
        return 0

    neo4j_db = os.getenv('NEO4J_DATABASE')
    dom = (domain or os.getenv('CPE_DOMAIN', 'curriculum')).strip().lower() or 'curriculum'
    prog_name = (program_name or os.getenv('CPE_PROGRAM_NAME') or dom).strip() or dom
    program_key = f"{dom}|{prog_name}".lower()

    def _do(tx):
        # Remove edges from program to courses/categories/semesters
        tx.run(
            """
            MATCH (p:Program {program_key:$program_key})
            OPTIONAL MATCH (p)-[r:HAS_COURSE|HAS_CATEGORY|HAS_SEMESTER_PLAN]->()
            DELETE r
            """,
            program_key=program_key,
        )

        # Delete Category and SemesterPlan nodes for this program
        tx.run(
            """
            MATCH (p:Program {program_key:$program_key})
            OPTIONAL MATCH (p)-[:HAS_CATEGORY]->(cat:Category)
            DETACH DELETE cat
            """,
            program_key=program_key,
        )
        tx.run(
            """
            MATCH (p:Program {program_key:$program_key})
            OPTIONAL MATCH (p)-[:HAS_SEMESTER_PLAN]->(s:SemesterPlan)
            DETACH DELETE s
            """,
            program_key=program_key,
        )

    with drv.session(database=neo4j_db) as session:
        session.execute_write(_do)

    try:
        drv.close()
    except Exception:
        pass

    return 1


def upsert_chunks_to_neo4j(chunks: Iterable[Dict[str, Any]], domain: Optional[str] = None) -> int:
    """Upsert chunk nodes and Course mentions into Neo4j.

    This is intentionally lightweight: it links course codes to chunks via (:Course)-[:MENTIONED_IN]->(:Chunk).
    If Neo4j env vars are not configured, it becomes a no-op.

        Required env:
            - NEO4J_URI (e.g. bolt://localhost:7687)
            - NEO4J_USERNAME (or NEO4J_USER)
            - NEO4J_PASSWORD
    """
    drv = _neo4j_driver()
    if not drv:
        return 0

    neo4j_db = os.getenv('NEO4J_DATABASE')

    domain = (domain or os.getenv('CPE_DOMAIN', 'curriculum')).strip().lower() or 'curriculum'

    rows: List[Tuple[str, str, int, int, int, List[str]]] = []
    for c in chunks:
        doc_id = str(c.get('doc_id') or '')
        if not doc_id:
            continue
        text = str(c.get('text') or '')
        path = str(c.get('path') or '')
        try:
            page_start = int(c.get('page_start') or 0)
        except Exception:
            page_start = 0
        try:
            page_end = int(c.get('page_end') or page_start)
        except Exception:
            page_end = page_start
        try:
            chunk_id = int(c.get('chunk_id') or 0)
        except Exception:
            chunk_id = 0
        codes = sorted(_extract_course_codes(text))
        # Store only lightweight metadata in Neo4j; full text stays in SQLite/Chroma
        rows.append((doc_id, path, page_start, page_end, chunk_id, codes))

    if not rows:
        return 0

    def _apply_schema(tx):
        _ensure_schema(tx)

    def _upsert_batch(tx, batch_rows):
        tx.run(
            """
            UNWIND $rows AS r
            MERGE (d:Document {doc_key: r.doc_key})
            SET d.path = r.path,
                d.domain = $domain
            MERGE (ch:Chunk {doc_id: r.doc_id})
            SET ch.path = r.path,
                ch.page_start = r.page_start,
                ch.page_end = r.page_end,
                ch.chunk_id = r.chunk_id,
                ch.domain = $domain
            MERGE (d)-[:HAS_CHUNK]->(ch)
            WITH ch, r
            UNWIND r.codes AS code
            MERGE (co:Course {code: code})
            MERGE (co)-[:MENTIONED_IN]->(ch)
            """,
            rows=batch_rows,
            domain=domain,
        )

    def _upsert_next_edges(tx, edges_rows):
        tx.run(
            """
            UNWIND $edges AS e
            MATCH (a:Chunk {doc_id: e.a})
            MATCH (b:Chunk {doc_id: e.b})
            MERGE (a)-[:NEXT {domain:$domain}]->(b)
            """,
            edges=edges_rows,
            domain=domain,
        )

    with drv.session(database=neo4j_db) as session:
        # Neo4j Aura forbids mixing schema modification + writes in one transaction.
        session.execute_write(_apply_schema)

        batch_size = int(os.getenv('NEO4J_UPSERT_BATCH', '200'))
        total = len(rows)
        sent = 0
        # Build NEXT edges per document (best-effort ordering)
        by_path: Dict[str, List[Tuple[int, int, str]]] = {}
        for (doc_id, path, page_start, _page_end, chunk_id, _codes) in rows:
            by_path.setdefault(path, []).append((page_start, chunk_id, doc_id))
        edges: List[Dict[str, str]] = []
        for path, items in by_path.items():
            items.sort(key=lambda x: (x[0], x[1]))
            for j in range(len(items) - 1):
                edges.append({'a': items[j][2], 'b': items[j+1][2]})

        for i in range(0, total, batch_size):
            sub = rows[i:i+batch_size]
            batch_rows = [
                {
                    'doc_id': doc_id,
                    'path': path,
                    'page_start': page_start,
                    'page_end': page_end,
                    'chunk_id': chunk_id,
                    'doc_key': f"{domain}|{path}",
                    'codes': codes,
                }
                for (doc_id, path, page_start, page_end, chunk_id, codes) in sub
            ]
            session.execute_write(_upsert_batch, batch_rows)
            sent += len(sub)
            if sent % (batch_size * 5) == 0 or sent == total:
                print(f"[Neo4j] Upserted {sent}/{total} chunks...")

        # NEXT edges in separate write batches
        if edges:
            total_e = len(edges)
            done = 0
            for i in range(0, total_e, batch_size * 2):
                sube = edges[i:i + batch_size * 2]
                session.execute_write(_upsert_next_edges, sube)
                done += len(sube)
                if done % (batch_size * 10) == 0 or done == total_e:
                    print(f"[Neo4j] Upserted NEXT {done}/{total_e} edges...")

    try:
        drv.close()
    except Exception:
        pass

    return len(rows)
