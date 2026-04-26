from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .config import DOMAIN, INDEX_ROOT


COURSE_CODE_RE = re.compile(r"\b([A-Za-z]{2,6})\s*[- ]?\s*(\d{3})\b")
PREREQ_MARKER_RE = re.compile(r"(วิชาบังคับก่อน|บังคับก่อน|ต้องผ่าน|prerequisite|pre-req)", re.IGNORECASE)


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


def write_structured_artifacts(files: list[Path]) -> list[str]:
    outputs: list[str] = []
    if DOMAIN == 'announcements':
        outputs.append(_write_json('announcement_calendar.json', _build_announcement_calendar(files)))
    elif DOMAIN == 'curriculum':
        outputs.append(_write_json('course_prerequisites.json', _build_course_prerequisites(files)))
    elif DOMAIN == 'regulations':
        outputs.append(_write_json('regulation_clauses.json', _build_regulation_clauses(files)))
    return outputs
