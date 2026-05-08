from __future__ import annotations

import csv
import json
import os
import re
import requests
from pathlib import Path
from typing import Any

from .config import DOMAIN, INDEX_ROOT
from .document_profiles import infer_document_profile


COURSE_CODE_RE = re.compile(r"\b([A-Za-z]{2,6})\s*[- ]?\s*(\d{3})\b")
PREREQ_MARKER_RE = re.compile(r"(วิชาบังคับก่อน|บังคับก่อน|ต้องผ่าน|prerequisite|pre-req)", re.IGNORECASE)
PHONE_RE = re.compile(r"(\b0\d{1,2}[- ]?\d{3}[- ]?\d{4}\b|\b0\d{2}[- ]?\d{3}[- ]?\d{3,4}\b)")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
URL_RE = re.compile(r"https?://\S+")
DATE_RE = re.compile(r"(\d{1,2}\s*(?:ม\.ค\.|ก\.พ\.|มี\.ค\.|เม\.ย\.|พ\.ค\.|มิ\.ย\.|ก\.ค\.|ส\.ค\.|ก\.ย\.|ต\.ค\.|พ\.ย\.|ธ\.ค\.)\s*(?:25\d{2}|26\d{2})|\d{1,2}\s*[/-]\s*\d{1,2}\s*[/-]\s*(?:25\d{2}|26\d{2}))")
COURSE_LINE_RE = re.compile(
    r"(?P<code>[A-Z]{2,6}\s*\d{3})\s+(?P<title>[^\n]+?)\s+(?P<credits>\d+\s*\(\d+\s*[-–]\s*\d+\s*[-–]\s*\d+\))",
    re.IGNORECASE,
)
INSTRUCTOR_NAME_RE = re.compile(r"(?:อาจารย์|อ\.|ผศ\.ดร\.|รศ\.ดร\.|ผศ\.|รศ\.|ศ\.|ดร\.)\s*([ก-๙A-Za-z]+(?:\s+[ก-๙A-Za-z]+){0,4})")
COURSE_START_RE = re.compile(r"^(?P<code>[A-Z]{2,6}\s*\d{3})\s+(?P<title>.+)$")
CREDITS_RE = re.compile(r"\d+\s*\(\d+\s*[-–]\s*\d+\s*[-–]\s*\d+\)")
BLOCK_SPLIT_RE = re.compile(r"\n\s*=+\s*\n")
THAI_PARENS_RE = re.compile(r"^\((?P<title>[ก-๙0-9A-Za-z\s\-/,&]+)\)$")
STEP_LINE_RE = re.compile(r"^\s*(\d+[\).\]])\s*(.+)$")
_FACT_LLM_ENABLE = (os.getenv('STRUCTURED_FACT_LLM_ENABLE', '0') or '0').strip().lower() in ('1', 'true', 'yes', 'on')
_THAI_MONTHS = {
    'ม.ค.': 1, 'มกราคม': 1,
    'ก.พ.': 2, 'กุมภาพันธ์': 2,
    'มี.ค.': 3, 'มีนาคม': 3,
    'เม.ย.': 4, 'เมษายน': 4,
    'พ.ค.': 5, 'พฤษภาคม': 5,
    'มิ.ย.': 6, 'มิถุนายน': 6,
    'ก.ค.': 7, 'กรกฎาคม': 7,
    'ส.ค.': 8, 'สิงหาคม': 8,
    'ก.ย.': 9, 'กันยายน': 9,
    'ต.ค.': 10, 'ตุลาคม': 10,
    'พ.ย.': 11, 'พฤศจิกายน': 11,
    'ธ.ค.': 12, 'ธันวาคม': 12,
}
_THAI_DATE_RE = re.compile(
    r"(?:วัน)?(?:จันทร์|อังคาร|พุธ|พฤหัสบดี|ศุกร์|เสาร์|อาทิตย์)?ที่?\s*"
    r"(?P<day>\d{1,2})\s*(?P<month>ม\.ค\.|ก\.พ\.|มี\.ค\.|เม\.ย\.|พ\.ค\.|มิ\.ย\.|ก\.ค\.|ส\.ค\.|ก\.ย\.|ต\.ค\.|พ\.ย\.|ธ\.ค\.|มกราคม|กุมภาพันธ์|มีนาคม|เมษายน|พฤษภาคม|มิถุนายน|กรกฎาคม|สิงหาคม|กันยายน|ตุลาคม|พฤศจิกายน|ธันวาคม)\s*"
    r"(?P<year>25\d{2}|26\d{2})"
)
_THAI_DATE_NO_YEAR_RE = re.compile(
    r"(?:วัน)?(?:จันทร์|อังคาร|พุธ|พฤหัสบดี|ศุกร์|เสาร์|อาทิตย์)?ที่?\s*"
    r"(?P<day>\d{1,2})\s*(?P<month>ม\.ค\.|ก\.พ\.|มี\.ค\.|เม\.ย\.|พ\.ค\.|มิ\.ย\.|ก\.ค\.|ส\.ค\.|ก\.ย\.|ต\.ค\.|พ\.ย\.|ธ\.ค\.|มกราคม|กุมภาพันธ์|มีนาคม|เมษายน|พฤษภาคม|มิถุนายน|กรกฎาคม|สิงหาคม|กันยายน|ตุลาคม|พฤศจิกายน|ธันวาคม)"
)
_THAI_RANGE_RE = re.compile(
    r"(?P<day1>\d{1,2})\s*(?P<month1>ม\.ค\.|ก\.พ\.|มี\.ค\.|เม\.ย\.|พ\.ค\.|มิ\.ย\.|ก\.ค\.|ส\.ค\.|ก\.ย\.|ต\.ค\.|พ\.ย\.|ธ\.ค\.|มกราคม|กุมภาพันธ์|มีนาคม|เมษายน|พฤษภาคม|มิถุนายน|กรกฎาคม|สิงหาคม|กันยายน|ตุลาคม|พฤศจิกายน|ธันวาคม)"
    r"\s*[–-]\s*"
    r"(?P<day2>\d{1,2})\s*(?:(?P<month2>ม\.ค\.|ก\.พ\.|มี\.ค\.|เม\.ย\.|พ\.ค\.|มิ\.ย\.|ก\.ค\.|ส\.ค\.|ก\.ย\.|ต\.ค\.|พ\.ย\.|ธ\.ค\.|มกราคม|กุมภาพันธ์|มีนาคม|เมษายน|พฤษภาคม|มิถุนายน|กรกฎาคม|สิงหาคม|กันยายน|ตุลาคม|พฤศจิกายน|ธันวาคม)\s*)?"
    r"(?P<year>25\d{2}|26\d{2})"
)


def _fact_signature(fact: dict[str, Any]) -> str:
    entity = str(fact.get('entity_type') or '').strip().lower()
    if entity == 'course':
        return f"course:{_normalize_course_code(str(fact.get('course_code') or ''))}"
    if entity == 'course_instructor':
        return "|".join(
            [
                'course_instructor',
                _clean_line(str(fact.get('person_name') or '')).lower(),
                _normalize_course_code(str(fact.get('course_code') or '')),
                _clean_line(str(fact.get('teaching_part') or '')).lower(),
            ]
        )
    if entity == 'person_contact':
        return "|".join(
            [
                'person_contact',
                _clean_line(str(fact.get('person_name') or '')).lower(),
                _clean_line(str(fact.get('email') or '')).lower(),
                _clean_line(str(fact.get('phone') or '')).lower(),
            ]
        )
    if entity == 'form':
        return "|".join(['form', _clean_line(str(fact.get('form_code') or '')).lower(), _clean_line(str(fact.get('form_name') or '')).lower()])
    if entity == 'procedure':
        return "|".join(['procedure', _clean_line(str(fact.get('action_name') or '')).lower(), _clean_line(str(fact.get('related_form_code') or '')).lower()])
    if entity == 'calendar_event':
        return "|".join(['calendar_event', _clean_line(str(fact.get('event_name') or '')).lower(), _clean_line(str(fact.get('value') or '')).lower()])
    if entity == 'regulation':
        return "|".join(['regulation', _clean_line(str(fact.get('clause') or fact.get('topic') or '')).lower(), _clean_line(str(fact.get('rule_summary') or '')).lower()])
    return _clean_line(json.dumps(fact, ensure_ascii=False, sort_keys=True)).lower()


def _prefer_richer_fact(existing: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing or {})
    merged.update({k: v for k, v in (new or {}).items() if v not in (None, '', [], {})})
    existing_fill = sum(1 for v in (existing or {}).values() if v not in (None, '', [], {}))
    new_fill = sum(1 for v in (new or {}).values() if v not in (None, '', [], {}))
    merged['confidence'] = max(float(existing.get('confidence') or 0.0), float(new.get('confidence') or 0.0))
    if new_fill > existing_fill:
        return merged
    return merged if merged.get('blob') else dict(existing or new or {})


def _dedupe_and_merge_facts(facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    bank: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for fact in facts:
        if not isinstance(fact, dict):
            continue
        sig = _fact_signature(fact)
        if not sig:
            continue
        if sig in bank:
            bank[sig] = _prefer_richer_fact(bank[sig], fact)
        else:
            bank[sig] = fact
            order.append(sig)
    return [bank[sig] for sig in order]


def _maybe_llm_extract_json(prompt: str) -> dict[str, Any]:
    if not _FACT_LLM_ENABLE:
        return {}
    api_key = str(os.getenv('OPENAI_API_KEY') or '').strip()
    base_url = str(os.getenv('OPENAI_BASE_URL') or 'https://api.openai.com/v1').strip().rstrip('/')
    model = str(os.getenv('STRUCTURED_FACT_LLM_MODEL') or os.getenv('LLM_AUX_MODEL') or os.getenv('LLM_MODEL') or '').strip()
    if not api_key or not model:
        return {}
    try:
        resp = requests.post(
            f"{base_url}/chat/completions",
            headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
            json={
                'model': model,
                'temperature': 0,
                'messages': [
                    {'role': 'system', 'content': 'Extract only grounded fields from the provided text. Respond with JSON object only.'},
                    {'role': 'user', 'content': prompt[:12000]},
                ],
            },
            timeout=20,
        )
        if resp.status_code >= 300:
            return {}
        data = resp.json()
        raw = str((((data.get('choices') or [{}])[0].get('message') or {}).get('content')) or '').strip()
        match = re.search(r"\{[\s\S]*\}", raw)
        if not match:
            return {}
        obj = json.loads(match.group(0))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _llm_enrich_announcement_fact(fact: dict[str, Any], text: str) -> dict[str, Any]:
    if not _FACT_LLM_ENABLE or not isinstance(fact, dict):
        return fact
    entity = str(fact.get('entity_type') or '').strip().lower()
    if entity not in ('procedure', 'calendar_event', 'regulation'):
        return fact
    if entity == 'procedure' and fact.get('steps') and fact.get('submit_to'):
        return fact
    prompt = (
        "อ่านข้อความประกาศมหาวิทยาลัยด้านล่าง แล้วดึงเฉพาะข้อมูลที่ยืนยันได้จริงเป็น JSON object\n"
        f"entity_type={entity}\n"
        "fields:\n"
        "- procedure: steps, required_documents, submit_to, approver\n"
        "- calendar_event: start_date, end_date, target_group\n"
        "- regulation: conditions, exceptions\n\n"
        f"text:\n{text}"
    )
    extra = _maybe_llm_extract_json(prompt)
    if not extra:
        return fact
    enriched = dict(fact)
    for key, value in extra.items():
        if value not in (None, '', [], {}):
            enriched[key] = value
    enriched['blob'] = _fact_blob(entity, enriched.get('evidence_text'), *[v for k, v in enriched.items() if k not in ('blob',)])
    return enriched


def _be_to_iso(year_be: str, month: int, day: int) -> str:
    try:
        year_ad = int(year_be) - 543
        return f"{year_ad:04d}-{int(month):02d}-{int(day):02d}"
    except Exception:
        return ''


def _extract_term_and_year(text: str) -> tuple[str, str]:
    raw = str(text or '')
    term_match = re.search(r"(?:ภาค(?:การศึกษา)?ที่\s*([1-3])\s*/\s*(25\d{2}|26\d{2})|([1-3])\s*/\s*(25\d{2}|26\d{2}))", raw)
    if term_match:
        term_no = str(term_match.group(1) or term_match.group(3) or '').strip()
        academic_year = str(term_match.group(2) or term_match.group(4) or '').strip()
        return (f"{term_no}/{academic_year}" if term_no and academic_year else '', academic_year)
    year_match = re.search(r"(25\d{2}|26\d{2})", raw)
    return ('', str(year_match.group(1) or '').strip() if year_match else '')


def _academic_year_from_term(term: str, fallback_year: str) -> str:
    match = re.search(r"[1-3]\s*/\s*(25\d{2}|26\d{2})", str(term or ''))
    if match:
        return str(match.group(1) or '').strip()
    return str(fallback_year or '').strip()


def _extract_date_range_fields(text: str) -> dict[str, str]:
    raw = str(text or '')
    range_match = _THAI_RANGE_RE.search(raw)
    if range_match:
        month1 = _THAI_MONTHS.get(str(range_match.group('month1') or '').strip(), 0)
        month2 = _THAI_MONTHS.get(str(range_match.group('month2') or range_match.group('month1') or '').strip(), 0)
        year_be = str(range_match.group('year') or '').strip()
        start = _be_to_iso(year_be, month1, int(range_match.group('day1') or 0)) if month1 else ''
        end = _be_to_iso(year_be, month2, int(range_match.group('day2') or 0)) if month2 else ''
        if start or end:
            return {'start_date': start, 'end_date': end or start}
    matches = list(_THAI_DATE_RE.finditer(raw))
    if not matches:
        no_year = list(_THAI_DATE_NO_YEAR_RE.finditer(raw))
        year_match = re.search(r"(25\d{2}|26\d{2})", raw)
        if no_year and year_match:
            year_be = str(year_match.group(1) or '').strip()
            values: list[str] = []
            for match in no_year[:2]:
                month_no = _THAI_MONTHS.get(str(match.group('month') or '').strip(), 0)
                if month_no <= 0:
                    continue
                values.append(_be_to_iso(year_be, month_no, int(match.group('day') or 0)))
            if values:
                return {'start_date': values[0], 'end_date': values[-1]}
        return {'start_date': '', 'end_date': ''}
    values: list[str] = []
    for match in matches[:2]:
        month_no = _THAI_MONTHS.get(str(match.group('month') or '').strip(), 0)
        if month_no <= 0:
            continue
        values.append(_be_to_iso(str(match.group('year') or '').strip(), month_no, int(match.group('day') or 0)))
    if not values:
        return {'start_date': '', 'end_date': ''}
    if len(values) == 1:
        return {'start_date': values[0], 'end_date': values[0]}
    return {'start_date': values[0], 'end_date': values[1]}


def _build_document_profiles(files: list[Path]) -> dict[str, Any]:
    profiles: list[dict[str, Any]] = []
    for path in files:
        text = _read_text(path)
        profiles.append(infer_document_profile(str(path), text, domain_hint=DOMAIN))
    return {
        'domain': DOMAIN or 'general',
        'kind': 'document_profiles',
        'profiles': profiles,
    }


def _link_related_facts(facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not facts:
        return []
    contacts_by_name: dict[str, dict[str, Any]] = {}
    forms_by_code: dict[str, dict[str, Any]] = {}
    for fact in facts:
        if str(fact.get('entity_type') or '').strip().lower() == 'person_contact':
            contacts_by_name[_clean_line(str(fact.get('person_name') or '')).lower()] = fact
        if str(fact.get('entity_type') or '').strip().lower() == 'form':
            code_key = _clean_line(str(fact.get('form_code_normalized') or fact.get('form_code') or '')).lower()
            if code_key:
                forms_by_code[code_key] = fact

    linked: list[dict[str, Any]] = []
    for fact in facts:
        row = dict(fact)
        entity = str(row.get('entity_type') or '').strip().lower()
        if entity == 'course_instructor':
            name_key = _clean_line(str(row.get('person_name') or '')).lower()
            contact = contacts_by_name.get(name_key)
            if contact:
                row.setdefault('email', str(contact.get('email') or '').strip())
                row.setdefault('phone', str(contact.get('phone') or '').strip())
        if entity == 'procedure':
            form_key = _clean_line(str(row.get('related_form_code_normalized') or row.get('related_form_code') or '')).lower()
            linked_form = forms_by_code.get(form_key)
            if linked_form:
                row.setdefault('linked_form_name', str(linked_form.get('form_name') or '').strip())
                row.setdefault('linked_form_link', str(linked_form.get('link') or '').strip())
        row['blob'] = _fact_blob(entity, row.get('evidence_text'), *[v for k, v in row.items() if k not in ('blob',)])
        linked.append(row)
    return linked


def structured_dir() -> Path:
    if DOMAIN:
        out = INDEX_ROOT / DOMAIN / 'structured'
    else:
        out = INDEX_ROOT / 'structured'
    out.mkdir(parents=True, exist_ok=True)
    return out


def _write_json(filename: str, payload: dict[str, Any]) -> str:
    path = structured_dir() / filename
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    return str(path)


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return ''


def _normalize_course_code(code: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "", str(code or '').upper())


def _extract_course_codes(text: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for pref, num in COURSE_CODE_RE.findall(text or ''):
        code = f"{str(pref or '').upper()}{str(num or '')}"
        if code in seen:
            continue
        seen.add(code)
        out.append(code)
    return out


def _fact_blob(*parts: Any) -> str:
    return " ".join([str(p or "").strip() for p in parts if str(p or "").strip()]).strip()


def _fact_entry(entity_type: str, *, source_doc: str, source: str, page: int = 1, evidence_text: str = '', confidence: float = 0.8, **fields: Any) -> dict[str, Any]:
    payload = {
        'entity_type': entity_type,
        'source_doc': source_doc,
        'source': source,
        'page': int(page or 1),
        'evidence_text': re.sub(r"\s+", " ", str(evidence_text or '').strip()),
        'confidence': float(confidence or 0.0),
    }
    payload.update(fields)
    payload['blob'] = _fact_blob(entity_type, payload.get('evidence_text'), *fields.values())
    return payload


def _clean_line(line: str) -> str:
    return re.sub(r"\s+", " ", str(line or "").strip())


def _sanitize_title(value: str) -> str:
    text = _clean_line(value)
    return re.sub(r"\s*\*+update\**\s*", " ", text, flags=re.IGNORECASE).strip()


def _extract_form_code(text: str) -> str:
    code_match = re.search(r"\b(RO\s*[- ]?\s*\d{2}|ก\.ค\.\s*18|สทน\.\s*\d{2}|RO\.\d{2})\b", text, re.IGNORECASE)
    if not code_match:
        return ''
    raw_code = re.sub(r"\s+", "", str(code_match.group(1) or '').upper()).strip()
    raw_code = raw_code.replace('RO.', 'RO-').replace('RO-', 'RO').replace('RO', 'RO-')
    if raw_code.startswith('สทน.'):
        raw_code = raw_code.replace(' ', '')
    if raw_code == 'ก.ค.18':
        return 'ก.ค.18'
    return raw_code


def _split_blocks(text: str) -> list[str]:
    return [blk.strip() for blk in BLOCK_SPLIT_RE.split(text or '') if blk.strip()]


def _extract_curriculum_course_blocks(path: Path, text: str) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    lines = [line.rstrip() for line in text.splitlines()]
    seen: set[str] = set()
    idx = 0
    stop_markers = (
        'ผลลัพธ์การเรียนรู้',
        'learning outcomes',
        'หมายเหตุ',
        '<page_number>',
        'level ',
    )

    while idx < len(lines):
        line = _clean_line(lines[idx])
        match = COURSE_START_RE.match(line)
        if not match:
            idx += 1
            continue
        code = _clean_line(match.group('code')).upper()
        course_key = _normalize_course_code(code)
        title_line = _clean_line(match.group('title'))
        window = [line]
        lookahead = idx + 1
        while lookahead < len(lines) and len(window) < 14:
            candidate = _clean_line(lines[lookahead])
            if not candidate:
                window.append(candidate)
                lookahead += 1
                continue
            next_match = COURSE_START_RE.match(candidate)
            if next_match and _normalize_course_code(_clean_line(next_match.group('code')).upper()) != course_key:
                break
            window.append(candidate)
            lower_candidate = candidate.lower()
            if any(marker in lower_candidate for marker in stop_markers):
                break
            lookahead += 1

        window_text = "\n".join([w for w in window if w])
        credits_match = CREDITS_RE.search(window_text)
        credits = _clean_line(credits_match.group(0)) if credits_match else ''
        title_no_credit = _clean_line(CREDITS_RE.sub('', title_line)).strip(' -')
        thai_title = ''
        english_title = title_no_credit

        thai_in_title = re.search(r"\(([^)]+)\)", title_no_credit)
        if thai_in_title and re.search(r"[ก-๙]", thai_in_title.group(1)):
            thai_title = _clean_line(thai_in_title.group(1))
            english_title = _clean_line(title_no_credit[:thai_in_title.start()]).strip(' -')
        else:
            for candidate in window[1:4]:
                thai_match = THAI_PARENS_RE.match(candidate)
                if thai_match and re.search(r"[ก-๙]", thai_match.group('title')):
                    thai_title = _clean_line(thai_match.group('title'))
                    break

        prereq = ''
        desc_th = ''
        desc_en = ''
        for pos, candidate in enumerate(window[1:], start=1):
            lowered = candidate.lower()
            if lowered.startswith('pre-requisite'):
                prereq = _clean_line(candidate.split(' ', 1)[1] if ' ' in candidate else candidate.replace('Pre-requisite', '').strip())
                continue
            if not candidate or candidate.startswith('(') or CREDITS_RE.search(candidate) or candidate.startswith('<page_number>'):
                continue
            if any(marker in lowered for marker in stop_markers):
                break
            if not desc_en and re.search(r"[A-Za-z]", candidate):
                desc_en = candidate
                continue
            if not desc_th and re.search(r"[ก-๙]", candidate):
                desc_th = candidate
                break

        if course_key and course_key not in seen:
            seen.add(course_key)
            facts.append(
                _fact_entry(
                    'course',
                    source_doc=path.name,
                    source=path.name,
                    evidence_text=_fact_blob(code, english_title, thai_title, credits, prereq),
                    confidence=0.95 if credits else 0.88,
                    course_code=code,
                    course_code_normalized=_normalize_course_code(code),
                    course_name=thai_title or english_title,
                    course_name_th=thai_title,
                    course_name_en=english_title,
                    credits=credits,
                    prerequisites=prereq,
                    required_status='unknown',
                    description_th=desc_th,
                    description_en=desc_en,
                )
            )
        idx = max(idx + 1, lookahead)
    return facts


def _extract_curriculum_teacher_profiles(path: Path) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    seen_assignments: set[str] = set()
    seen_courses: set[str] = set()
    try:
        with path.open(encoding='utf-8-sig', newline='') as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                course_code = _clean_line(row.get('course_code') or '').upper()
                person_name = _clean_line(row.get('name') or '')
                course_title = _clean_line(row.get('course_title_th') or '')
                level = _clean_line(row.get('level') or '')
                teaching_part = _clean_line(row.get('teaching_part') or '')
                credits = _clean_line(row.get('credits') or '')
                if not course_code or not person_name:
                    continue
                assignment_key = "|".join([person_name, course_code, teaching_part, level])
                if assignment_key not in seen_assignments:
                    seen_assignments.add(assignment_key)
                    facts.append(
                        _fact_entry(
                            'course_instructor',
                            source_doc=path.name,
                            source=path.name,
                            evidence_text=_fact_blob(person_name, course_code, course_title, level, teaching_part),
                            confidence=0.97,
                            person_name=person_name,
                            course_code=course_code,
                            course_code_normalized=_normalize_course_code(course_code),
                            course_name=course_title,
                            level=level,
                            teaching_part=teaching_part,
                            credits=credits,
                        )
                    )
                course_key = _normalize_course_code(course_code)
                if course_key and course_key not in seen_courses:
                    seen_courses.add(course_key)
                    facts.append(
                        _fact_entry(
                            'course',
                            source_doc=path.name,
                            source=path.name,
                            evidence_text=_fact_blob(course_code, course_title, credits),
                            confidence=0.8,
                            course_code=course_code,
                            course_code_normalized=_normalize_course_code(course_code),
                            course_name=course_title,
                            course_name_th=course_title,
                            course_name_en='',
                            credits=credits,
                            required_status='unknown',
                        )
                    )
    except Exception:
        return facts
    return facts


def _extract_regulation_form_blocks(path: Path, text: str) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for block in _split_blocks(text):
        title_match = re.search(r"ชื่อเอกสาร:\s*(.+)", block)
        desc_match = re.search(r"รายละเอียด:\s*(.+)", block)
        url_match = URL_RE.search(block)
        if not title_match:
            continue
        title = _sanitize_title(title_match.group(1))
        desc = _clean_line(desc_match.group(1)) if desc_match else ''
        url = _clean_line(url_match.group(0)) if url_match else ''
        form_code = _extract_form_code(_fact_blob(title, desc, url))
        facts.append(
                _fact_entry(
                    'form',
                source_doc=path.name,
                source=path.name,
                evidence_text=_fact_blob(title, desc, url),
                confidence=0.94,
                    form_code=form_code,
                    form_code_normalized=_clean_line(form_code).upper(),
                    form_name=title,
                purpose=desc,
                link=url,
            )
        )
        facts.append(
                _fact_entry(
                    'procedure',
                source_doc=path.name,
                source=path.name,
                evidence_text=_fact_blob(title, desc),
                confidence=0.72,
                action_name=title,
                steps='ดาวน์โหลดแบบฟอร์มจากลิงก์ที่ระบุและยื่นตามวัตถุประสงค์ของเอกสาร',
                required_documents='ยังไม่ระบุชัดในเอกสารนี้',
                submit_to='ยังไม่ระบุชัดในเอกสารนี้',
                approver='ยังไม่ระบุชัดในเอกสารนี้',
                    related_form_code=form_code,
                    related_form_code_normalized=_clean_line(form_code).upper(),
                )
            )
    return facts


def _extract_regulation_contact_blocks(path: Path, text: str) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    seen: set[str] = set()
    for block in _split_blocks(text):
        name_match = re.search(r"ชื่อ:\s*(.+)", block)
        if not name_match:
            continue
        person_name = _clean_line(name_match.group(1))
        phone_match = re.search(r"โทร:\s*(.+)", block)
        email_match = re.search(r"อีเมล:\s*(.+)", block)
        phone = _clean_line(phone_match.group(1)) if phone_match else ''
        email = _clean_line(email_match.group(1)) if email_match else ''
        if phone == '-':
            phone = ''
        if email == '-':
            email = ''
        key = "|".join([person_name, phone, email])
        if key in seen:
            continue
        seen.add(key)
        facts.append(
            _fact_entry(
                'person_contact',
                source_doc=path.name,
                source=path.name,
                evidence_text=_fact_blob(person_name, phone, email),
                confidence=0.93,
                person_name=person_name,
                phone=phone,
                email=email,
            )
        )
    return facts


def _extract_announcement_facts(path: Path, text: str) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    lines = [_clean_line(line) for line in text.splitlines()]
    current_topic = ''
    procedure_steps: list[str] = []
    procedure_active = False
    download_active = False
    procedure_intro: list[str] = []

    for idx, line in enumerate(lines):
        if not line:
            continue
        if line.startswith(('🔸', '🔹', '📢', '📌')):
            current_topic = line.lstrip('🔸🔹📢📌').strip()
        if line.lower().startswith('download'):
            download_active = True
            procedure_active = False
            continue
        if 'ขั้นตอนการถอนรายวิชาออนไลน์ผ่านระบบ' in line:
            procedure_active = True
            download_active = False
            procedure_intro = [current_topic or 'ถอนรายวิชาออนไลน์']
            continue
        if 'นักศึกษาที่ประสงค์จะลดรายวิชา' in line or line.startswith('ให้ยื่น'):
            procedure_intro.append(line)
            continue
        if 'ผลการประเมินเป็น' in line and 'W' in line:
            facts.append(
                _fact_entry(
                    'regulation',
                    source_doc=path.name,
                    source=path.name,
                    evidence_text=line,
                    confidence=0.95,
                    topic='withdrawal_result',
                    rule_summary=line,
                    conditions='ได้รับผลการประเมินเป็น W เมื่อถอนรายวิชาในช่วงเวลาที่ประกาศ',
                )
            )
            continue
        if download_active:
            url_match = URL_RE.search(line)
            if url_match:
                label = _clean_line(line[:url_match.start()]).strip(':')
                form_code = _extract_form_code(label or line)
                facts.append(
                    _fact_entry(
                        'form',
                        source_doc=path.name,
                        source=path.name,
                        evidence_text=line,
                        confidence=0.9,
                        form_code=form_code,
                        form_code_normalized=_clean_line(form_code).upper(),
                        form_name=label or form_code or 'คำร้อง',
                        purpose=current_topic or 'ประกาศที่เกี่ยวข้องกับการลงทะเบียน',
                        link=_clean_line(url_match.group(0)),
                    )
                )
                continue
            if line.startswith('🔹') or line.startswith('🔸'):
                download_active = False
        step_match = STEP_LINE_RE.match(line)
        if procedure_active and step_match:
            procedure_steps.append(_clean_line(step_match.group(2)))
            continue
        if procedure_active and procedure_steps and (line.startswith('หมายเหตุ') or line.startswith('ตรวจสอบกำหนดการ')):
            procedure_steps.append(line)
            continue
        if procedure_active and procedure_steps and current_topic and line.startswith('การลงทะเบียน '):
            procedure_active = False

    if procedure_steps:
        related_codes = []
        for match in re.finditer(r"(สทน\.\s*\d{2}|RO\s*[- ]?\s*\d{2})", text, re.IGNORECASE):
            code = _extract_form_code(str(match.group(0) or ''))
            if code and code not in related_codes:
                related_codes.append(code)
        facts.append(
            _fact_entry(
                'procedure',
                source_doc=path.name,
                source=path.name,
                evidence_text=_fact_blob(*procedure_intro, *procedure_steps),
                confidence=0.94,
                action_name='ถอนรายวิชาออนไลน์',
                steps=' | '.join(procedure_steps),
                required_documents='คำร้องถอนรายวิชาผ่านเว็บ หรือแบบฟอร์มที่ประกาศกำหนด',
                submit_to='ระบบ https://sinfo.kmutt.ac.th/ หรือ pas.kmutt.ac.th/request/ ตามประกาศ',
                approver='ต้องได้รับการอนุมัติตามกระบวนการในระบบ',
                related_form_code=', '.join(related_codes),
                related_form_code_normalized=', '.join([_clean_line(v).upper() for v in related_codes]),
            )
        )
    return [_llm_enrich_announcement_fact(fact, text) for fact in facts]


def _build_announcement_calendar(files: list[Path]) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    current_topic = ''
    calendar_markers = (
        'ปฏิทินการศึกษา',
        'วันสุดท้ายของการชำระเงิน',
        'ระบบเปิดให้บริการ',
        'กำหนดการลดรายวิชา',
        'โมดูล 5 สัปดาห์',
        'อยู่ในระบบได้ครั้งละไม่เกิน',
    )
    for path in files:
        if not path.name.lower().endswith('.txt'):
            continue
        text = _read_text(path)
        if not text:
            continue
        if not any(marker in text for marker in calendar_markers):
            continue
        for raw_line in text.splitlines():
            line = re.sub(r"\s+", " ", raw_line.strip())
            if not line:
                continue
            if line.startswith(('🔸', '🔹', '📢', '📌')):
                current_topic = line.lstrip('🔸🔹📢📌').strip()
                continue
            if line.startswith(('http://', 'https://')):
                continue
            if 'ระบบเปิดให้บริการ เวลา' in line:
                m_time = re.search(r"(\d{1,2}:\d{2}\s*[–-]\s*\d{1,2}:\d{2}\s*น\.)", line)
                value = str(m_time.group(1) or line).strip() if m_time else line
                label = 'ระบบเปิดให้บริการ'
                entries.append(
                    {
                        'source': path.name,
                        'page': 1,
                        'label': label,
                        'value': value,
                        'topic': current_topic,
                        'keywords': [label, current_topic],
                        'blob': f"{current_topic} {label} {value}".strip(),
                    }
                )
                continue
            if 'นักศึกษาจะอยู่ในระบบได้ครั้งละไม่เกิน' in line:
                entries.append(
                    {
                        'source': path.name,
                        'page': 1,
                        'label': 'นักศึกษาจะอยู่ในระบบได้ครั้งละไม่เกิน',
                        'value': line,
                        'topic': current_topic,
                        'keywords': ['นักศึกษาจะอยู่ในระบบได้ครั้งละไม่เกิน', current_topic],
                        'blob': f"{current_topic} {line}".strip(),
                    }
                )
                continue
            if ':' in line:
                left, right = [part.strip() for part in line.split(':', 1)]
                if not right:
                    continue
                blob = f"{current_topic} {left} {right}".strip()
                keywords = [left]
                if current_topic:
                    keywords.append(current_topic)
                entries.append(
                    {
                        'source': path.name,
                        'page': 1,
                        'label': left,
                        'value': right,
                        'topic': current_topic,
                        'keywords': keywords,
                        'blob': blob,
                    }
                )
                continue
            if line.startswith('ระหว่าง ') and current_topic:
                entries.append(
                    {
                        'source': path.name,
                        'page': 1,
                        'label': current_topic,
                        'value': line.replace('ระหว่าง ', '', 1).strip(),
                        'topic': current_topic,
                        'keywords': [current_topic, 'ระหว่าง'],
                        'blob': f"{current_topic} {line}".strip(),
                    }
                )
                continue
            if ('ผลการประเมินเป็น' in line) or ('อยู่ในระบบได้ครั้งละไม่เกิน' in line) or ('ระบบเปิดให้บริการ เวลา' in line):
                label = current_topic or line
                entries.append(
                    {
                        'source': path.name,
                        'page': 1,
                        'label': label,
                        'value': line,
                        'topic': current_topic,
                        'keywords': [label],
                        'blob': f"{label} {line}".strip(),
                    }
                )

    return {
        'domain': 'announcements',
        'kind': 'announcement_calendar',
        'entries': entries,
    }


def _build_course_prerequisites(files: list[Path]) -> dict[str, Any]:
    combined_parts: list[tuple[str, str]] = []
    for path in files:
        if not path.name.lower().endswith('.txt'):
            continue
        text = _read_text(path)
        if not text.strip():
            continue
        combined_parts.append((path.name, text))

    course_codes: set[str] = set()
    for _src, text in combined_parts:
        for code in _extract_course_codes(text):
            course_codes.add(code)

    entries: dict[str, dict[str, Any]] = {}
    for code in sorted(course_codes):
        pref = code[:-3]
        num = code[-3:]
        code_re = re.compile(rf"\b{re.escape(pref)}\s*[- ]?\s*{re.escape(num)}\b", re.IGNORECASE)
        for src, text in combined_parts:
            if not code_re.search(text):
                continue
            if code_re.search(text) and re.search(r"(ไม่มีวิชาบังคับก่อน|ไม่มี\s*prerequisite)", text, re.IGNORECASE):
                entries.setdefault(
                    code,
                    {
                        'course_code': code,
                        'prerequisites': [],
                        'source': src,
                        'page': 1,
                    },
                )
            for mc in code_re.finditer(text):
                s = max(0, mc.start() - 260)
                e = min(len(text), mc.end() + 420)
                win = text[s:e]
                pre_local = text[max(0, mc.start() - 64):mc.start()]
                post_local = text[mc.end():min(len(text), mc.end() + 360)]
                if PREREQ_MARKER_RE.search(pre_local):
                    continue
                if not PREREQ_MARKER_RE.search(post_local):
                    continue
                found: list[str] = []
                for p2, n2 in COURSE_CODE_RE.findall(win):
                    other = f"{str(p2 or '').upper()}{str(n2 or '')}"
                    if other == code:
                        continue
                    disp = f"{other[: len(other) - 3]} {other[-3:]}"
                    if disp not in found:
                        found.append(disp)
                if re.search(r"\bO\s*-?\s*NET\b|โอ\s*-?\s*เน็ต", win, re.IGNORECASE) and 'O-NET' not in found:
                    found.append('O-NET')
                if found:
                    entries[code] = {
                        'course_code': code,
                        'prerequisites': found,
                        'source': src,
                        'page': 1,
                    }
                    break
            if code in entries and entries[code].get('prerequisites'):
                break

    return {
        'domain': 'curriculum',
        'kind': 'course_prerequisites',
        'entries': entries,
    }


def _build_regulation_clauses(files: list[Path]) -> dict[str, Any]:
    clauses: dict[str, dict[str, Any]] = {}
    for path in files:
        if not path.name.lower().endswith('.txt'):
            continue
        if 'rule_exam' not in path.name.lower():
            continue
        text = _read_text(path)
        if not text:
            continue
        for m in re.finditer(
            r"(ข้อ\s*([๐-๙0-9]+(?:\.[๐-๙0-9]+)?)\s.*?)(?=ข้อ\s*[๐-๙0-9]+(?:\.[๐-๙0-9]+)?|$)",
            text,
            flags=re.DOTALL,
        ):
            raw = str(m.group(1) or '').strip()
            clause = str(m.group(2) or '').translate(str.maketrans('๐๑๒๓๔๕๖๗๘๙', '0123456789')).strip()
            if not clause or clause in clauses:
                continue
            clauses[clause] = {
                'clause': clause,
                'text': re.sub(r"\s+", " ", raw),
                'source': path.name,
                'page': 1,
            }
        for sub in re.finditer(r"((28\.[12])\s+.*?)(?=28\.[12]\s+|ข้อ\s*29|$)", text, flags=re.DOTALL):
            raw = str(sub.group(1) or '').strip()
            clause = str(sub.group(2) or '').strip()
            clauses[clause] = {
                'clause': clause,
                'text': re.sub(r"\s+", " ", raw),
                'source': path.name,
                'page': 1,
            }

    return {
        'domain': 'regulations',
        'kind': 'regulation_clauses',
        'entries': clauses,
    }


def _build_fact_index(files: list[Path]) -> dict[str, Any]:
    facts: list[dict[str, Any]] = []

    if DOMAIN == 'curriculum':
        seen_contacts: set[str] = set()
        for path in files:
            if not path.name.lower().endswith(('.txt', '.csv', '.tsv')):
                continue
            if path.name.lower().endswith('.csv') and 'teacher_profiles' in path.name.lower():
                facts.extend(_extract_curriculum_teacher_profiles(path))
                continue
            text = _read_text(path)
            if not text:
                continue
            course_facts = _extract_curriculum_course_blocks(path, text)
            if course_facts:
                facts.extend(course_facts)
            for m in COURSE_LINE_RE.finditer(text):
                code = re.sub(r"\s+", " ", str(m.group('code') or '').upper()).strip()
                key = _normalize_course_code(code)
                if not key or any(_normalize_course_code(f.get('course_code') or '') == key for f in facts if f.get('entity_type') == 'course'):
                    continue
                title = re.sub(r"\s+", " ", str(m.group('title') or '').strip())
                credits = re.sub(r"\s+", " ", str(m.group('credits') or '').strip())
                is_required = 'บังคับ' in text or 'required' in text.lower()
                facts.append(
                    _fact_entry(
                        'course',
                        source_doc=path.name,
                        source=path.name,
                        evidence_text=f"{code} {title} {credits}",
                        confidence=0.9,
                        course_code=code,
                        course_name=title,
                        credits=credits,
                        required_status='required' if is_required else 'unknown',
                    )
                )
            for raw_line in text.splitlines():
                line = re.sub(r"\s+", " ", raw_line.strip())
                if not line:
                    continue
                email_match = EMAIL_RE.search(line)
                phone_match = PHONE_RE.search(line)
                if not (email_match or phone_match):
                    continue
                name_match = INSTRUCTOR_NAME_RE.search(line)
                if not name_match:
                    continue
                person_name = re.sub(r"\s+", " ", str(name_match.group(0) or '').strip())
                contact_key = f"{path.name}:{person_name}:{email_match.group(0) if email_match else ''}:{phone_match.group(0) if phone_match else ''}"
                if contact_key in seen_contacts:
                    continue
                seen_contacts.add(contact_key)
                facts.append(
                    _fact_entry(
                        'person_contact',
                        source_doc=path.name,
                        source=path.name,
                        evidence_text=line,
                        confidence=0.82,
                        person_name=person_name,
                        email=str(email_match.group(0) or '').strip() if email_match else '',
                        phone=str(phone_match.group(0) or '').strip() if phone_match else '',
                    )
                )

    elif DOMAIN == 'announcements':
        calendar = _build_announcement_calendar(files)
        announcement_defaults: dict[str, tuple[str, str]] = {}
        for path in files:
            if path.name.lower().endswith('.txt'):
                announcement_defaults[path.name] = _extract_term_and_year(_read_text(path))
        for entry in list(calendar.get('entries') or []):
            if not isinstance(entry, dict):
                continue
            event_text = str(entry.get('blob') or entry.get('value') or '').strip()
            entry_term, entry_year = _extract_term_and_year(event_text)
            default_term, default_year = announcement_defaults.get(str(entry.get('source') or ''), ('', ''))
            final_term = entry_term or default_term
            final_year = _academic_year_from_term(final_term, entry_year or default_year)
            facts.append(
                _fact_entry(
                    'calendar_event',
                    source_doc=str(entry.get('source') or 'announcement_calendar.json'),
                    source=str(entry.get('source') or 'announcement_calendar.json'),
                    page=int(entry.get('page') or 1),
                    evidence_text=str(entry.get('blob') or entry.get('value') or '').strip(),
                    confidence=0.9,
                    event_name=str(entry.get('label') or '').strip(),
                    topic=str(entry.get('topic') or '').strip(),
                    value=str(entry.get('value') or '').strip(),
                    term=final_term,
                    academic_year=final_year,
                    **_extract_date_range_fields(event_text),
                )
            )
        for path in files:
            if path.name.lower().endswith('.txt'):
                facts.extend(_extract_announcement_facts(path, _read_text(path)))

    elif DOMAIN == 'regulations':
        clauses = _build_regulation_clauses(files)
        for clause_id, entry in dict(clauses.get('entries') or {}).items():
            if not isinstance(entry, dict):
                continue
            facts.append(
                _fact_entry(
                    'regulation',
                    source_doc=str(entry.get('source') or 'regulation_clauses.json'),
                    source=str(entry.get('source') or 'regulation_clauses.json'),
                    page=int(entry.get('page') or 1),
                    evidence_text=str(entry.get('text') or '').strip(),
                    confidence=0.88,
                    clause=str(clause_id or '').strip(),
                    topic='exam_regulation',
                )
            )
        for path in files:
            text = _read_text(path)
            if not text:
                continue
            if path.name.lower() == 'forms.txt':
                facts.extend(_extract_regulation_form_blocks(path, text))
            elif path.name.lower() == 'contacts.txt':
                facts.extend(_extract_regulation_contact_blocks(path, text))

    facts = _dedupe_and_merge_facts(facts)
    facts = _link_related_facts(facts)
    return {
        'domain': DOMAIN or 'general',
        'kind': 'fact_index',
        'facts': facts,
    }


def write_structured_artifacts(files: list[Path]) -> list[str]:
    outputs: list[str] = []
    outputs.append(_write_json('document_profiles.json', _build_document_profiles(files)))
    if DOMAIN == 'announcements':
        outputs.append(_write_json('announcement_calendar.json', _build_announcement_calendar(files)))
    elif DOMAIN == 'curriculum':
        outputs.append(_write_json('course_prerequisites.json', _build_course_prerequisites(files)))
    elif DOMAIN == 'regulations':
        outputs.append(_write_json('regulation_clauses.json', _build_regulation_clauses(files)))
    if DOMAIN in ('announcements', 'curriculum', 'regulations'):
        outputs.append(_write_json('fact_index.json', _build_fact_index(files)))
    return outputs
