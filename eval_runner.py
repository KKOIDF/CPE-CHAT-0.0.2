#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import requests


KNOWN_DOMAINS = {"curriculum", "regulations", "announcements"}
CITATION_RE = re.compile(r"\[([^\[\]/]+?)/(\d+)\]")

DEFAULT_PRODUCTION_CATEGORY_MIN_OVERALL = {
    "regulations": 0.90,
    "curriculum_fact_lookup": 0.90,
    "announcements": 0.75,
}

DEFAULT_PRODUCTION_DOMAIN_MAX_P95_LATENCY_MS = {
    "announcements": 1400.0,
    "regulations": 2500.0,
    "curriculum": 2000.0,
    "multi": 2200.0,
}


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def normalize_source_token(text: str) -> str:
    s = (text or "").strip().lower().replace("\\", "/")
    s = s.split("/")[-1]
    s = s.replace(".txt", "")
    return re.sub(r"[^a-z0-9ก-๙]+", "", s)


def source_token_variants(text: str) -> set[str]:
    raw = str(text or "").strip().lower().replace("\\", "/")
    out: set[str] = set()

    base = normalize_source_token(raw)
    if base:
        out.add(base)

    tail = raw.split("/")[-1]
    stem = tail.replace(".txt", "")
    for part in re.split(r"[^a-z0-9ก-๙]+", stem):
        tok = normalize_source_token(part)
        if tok:
            out.add(tok)

    # Domain aliases help when expected tokens include logical source family names.
    if any(k in raw for k in ("foe10", "curriculum", "หลักสูตร", "วศ.บ", "วศ_บ")):
        out.update({"foe10", "curriculum"})
    if any(k in raw for k in ("rule_exam", "ruleg", "regulation", "ระเบียบ")):
        out.update({"ruleexam2560", "ruleexam", "regulation", "regulations"})
    if any(k in raw for k in ("announce", "announcement", "calendar", "ปฏิทิน")):
        out.update({"announcement", "announcements", "calendar"})

    return {t for t in out if t}


def source_token_matches(left: str, right: str) -> bool:
    a = normalize_source_token(left)
    b = normalize_source_token(right)
    if not a or not b:
        return False
    if a == b:
        return True
    return a in b or b in a


def clamp01(value: float) -> float:
    try:
        v = float(value)
    except Exception:
        return 0.0
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = int(round((p / 100.0) * (len(ordered) - 1)))
    idx = max(0, min(idx, len(ordered) - 1))
    return float(ordered[idx])


def to_bool_or_none(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return None


def first_non_empty_str(*values: Any) -> str:
    for v in values:
        s = str(v or "").strip()
        if s:
            return s
    return ""


def context_similarity_score(ctx: dict[str, Any]) -> float | None:
    for key in ("score", "similarity", "similarity_score", "rerank_score", "vector_score"):
        try:
            raw = (ctx or {}).get(key)
            if raw is None:
                continue
            return float(raw)
        except Exception:
            continue
    return None


def top_context_rows(contexts: list[dict[str, Any]], k: int = 5) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for i, ctx in enumerate(contexts[: max(1, int(k))], start=1):
        src = first_non_empty_str((ctx or {}).get("source"), (ctx or {}).get("path"), (ctx or {}).get("doc_id"))
        rows.append(
            {
                "rank": i,
                "source": src,
                "domain": str((ctx or {}).get("domain") or "").strip().lower() or None,
                "similarity_score": context_similarity_score(ctx),
            }
        )
    return rows


def detect_system_abstain(answer: str) -> bool:
    txt = normalize_text(answer)
    if not txt:
        return True
    abstain_phrases = [
        "ไม่พบข้อมูล",
        "ไม่สามารถยืนยัน",
        "ไม่มีข้อมูล",
        "ไม่ทราบ",
        "insufficient information",
    ]
    return any(p in txt for p in abstain_phrases)


def case_error_tags(
    *,
    error: str,
    retrieval_hit_pass: bool,
    retrieval_domain_pass: bool,
    retrieval_source_pass: bool,
    answer_hit_pass: bool,
    citation_validity_pass: bool,
    must_not_contain_pass: bool,
    human_hallucination: bool | None,
) -> list[str]:
    tags: list[str] = []
    if error:
        tags.append("runtime_error")
    if not retrieval_hit_pass:
        if not retrieval_source_pass:
            tags.append("retrieve_not_found")
        if not retrieval_domain_pass:
            tags.append("answer_out_of_domain")
    if retrieval_hit_pass and not answer_hit_pass:
        tags.append("retrieve_found_but_answer_incomplete")
    if not citation_validity_pass:
        tags.append("context_conflict")
    if (human_hallucination is True) or (not must_not_contain_pass):
        tags.append("hallucination")
    if not tags:
        tags.append("pass_or_unclassified")
    # Keep stable order while removing duplicates.
    return list(dict.fromkeys(tags))


def parse_category_thresholds(text: str) -> dict[str, float]:
    out: dict[str, float] = {}
    for part in str(text or "").split(","):
        token = part.strip()
        if not token or "=" not in token:
            continue
        name, value = token.split("=", 1)
        cat = name.strip()
        if not cat:
            continue
        try:
            out[cat] = float(value.strip())
        except Exception:
            continue
    return out


def post_json(base_url: str, endpoint: str, payload: dict[str, Any], timeout_s: float) -> tuple[dict[str, Any], float, str]:
    url = base_url.rstrip("/") + endpoint
    started = time.perf_counter()
    try:
        response = requests.post(url, json=payload, timeout=timeout_s)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        response.raise_for_status()
        data = response.json() or {}
        return dict(data), elapsed_ms, ""
    except Exception as exc:  # pragma: no cover
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        return {}, elapsed_ms, f"{type(exc).__name__}: {exc}"


def case_conversation_id(case: dict[str, Any]) -> str:
    return first_non_empty_str(
        case.get("conversation_id"),
        case.get("session_id"),
        case.get("thread_id"),
    )


def case_turn_index(case: dict[str, Any], fallback_order: int) -> int:
    raw = case.get("turn_index")
    if raw is None or raw == "":
        return int(fallback_order)
    try:
        return int(raw)
    except Exception:
        return int(fallback_order)


def sort_cases_for_execution(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    indexed_cases = [(idx, case) for idx, case in enumerate(cases) if isinstance(case, dict)]
    first_seen: dict[str, int] = {}
    for idx, case in indexed_cases:
        cid = case_conversation_id(case)
        if cid and cid not in first_seen:
            first_seen[cid] = idx

    def _sort_key(item: tuple[int, dict[str, Any]]) -> tuple[int, int, int]:
        idx, case = item
        cid = case_conversation_id(case)
        if not cid:
            return (idx, 0, idx)
        return (first_seen.get(cid, idx), 1, case_turn_index(case, idx))

    ordered = sorted(indexed_cases, key=_sort_key)
    return [case for _, case in ordered]


def build_chat_messages(history: list[dict[str, str]], question: str) -> list[dict[str, str]]:
    messages = [dict(msg) for msg in (history or []) if isinstance(msg, dict)]
    messages.append({"role": "user", "content": str(question or "").strip()})
    return messages


def build_eval_request_payloads(
    case: dict[str, Any],
    conversation_history: list[dict[str, str]] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    question = str(case.get("question") or "").strip()
    expected_domain_raw = str(case.get("expected_domain") or "").strip().lower()
    expected_domain = expected_domain_raw if expected_domain_raw else None
    conversation_id = case_conversation_id(case)

    retrieval_payload: dict[str, Any] = {"question": question}
    answer_payload: dict[str, Any] = {"question": question, "eval_mode": True}
    if expected_domain in KNOWN_DOMAINS:
        retrieval_payload["domain"] = expected_domain
        answer_payload["domain"] = expected_domain

    if conversation_id:
        retrieval_payload["session_id"] = conversation_id
        answer_payload["session_id"] = conversation_id
        answer_payload["messages"] = build_chat_messages(conversation_history or [], question)

    return retrieval_payload, answer_payload, conversation_id


def get_json(base_url: str, endpoint: str, timeout_s: float) -> tuple[dict[str, Any], float, str]:
    url = base_url.rstrip("/") + endpoint
    started = time.perf_counter()
    try:
        response = requests.get(url, timeout=timeout_s)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        response.raise_for_status()
        data = response.json() or {}
        return dict(data), elapsed_ms, ""
    except Exception as exc:  # pragma: no cover
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        return {}, elapsed_ms, f"{type(exc).__name__}: {exc}"


def preflight_healthcheck(base_url: str, timeout_s: float, retries: int, interval_s: float) -> tuple[bool, str]:
    tries = max(1, int(retries))
    wait_s = max(0.0, float(interval_s))
    last_err = ""
    for i in range(1, tries + 1):
        data, elapsed_ms, err = get_json(base_url, "/health", timeout_s=timeout_s)
        if not err:
            status = str(data.get("status") or "").strip().lower()
            if status in {"ok", "ready", "healthy"}:
                print(
                    f"[heartbeat] preflight_ok attempt={i}/{tries} latency_ms={elapsed_ms:.1f} status={status}",
                    flush=True,
                )
                return True, ""
            last_err = f"unexpected health payload: {data}"
        else:
            last_err = err
        print(
            f"[heartbeat] preflight_retry attempt={i}/{tries} err={last_err}",
            flush=True,
        )
        if i < tries and wait_s > 0:
            time.sleep(wait_s)
    return False, last_err or "preflight healthcheck failed"


def answer_keyword_stats(answer: str, expected_keywords: list[str]) -> tuple[int, int, float, bool]:
    expected = [k for k in (expected_keywords or []) if str(k).strip()]
    if not expected:
        return 0, 0, 1.0, True
    normalized_answer = normalize_text(answer)
    matched = 0
    for kw in expected:
        if normalize_text(kw) in normalized_answer:
            matched += 1
    total = len(expected)
    coverage = matched / total if total else 1.0
    return matched, total, coverage, matched == total


def must_not_contain_ok(answer: str, forbidden_list: list[str]) -> bool:
    ans = normalize_text(answer)
    for token in forbidden_list or []:
        if normalize_text(token) and normalize_text(token) in ans:
            return False
    return True


def retrieval_hit(
    contexts: list[dict[str, Any]],
    expected_domain: str | None,
    expected_domains_any: list[str],
    expected_source_contains: list[str],
) -> tuple[bool, bool, bool, list[str], list[str], float, bool, int | None]:
    domains = [str((c or {}).get("domain") or "").strip().lower() for c in contexts or []]
    domain_set = {d for d in domains if d}

    source_haystacks: list[str] = []
    for ctx in contexts or []:
        src = str((ctx or {}).get("source") or (ctx or {}).get("path") or "").strip()
        dom = str((ctx or {}).get("domain") or "").strip()
        source_haystacks.append(normalize_text(f"{src} {dom}"))

    domain_ok = True
    if (expected_domain or "").strip().lower() in KNOWN_DOMAINS:
        domain_ok = (expected_domain or "").strip().lower() in domain_set

    domains_any_ok = True
    normalized_expected_domains_any = [d.strip().lower() for d in expected_domains_any or [] if d.strip()]
    if normalized_expected_domains_any:
        domains_any_ok = all(d in domain_set for d in normalized_expected_domains_any)

    missing_source_tokens: list[str] = []
    for token in expected_source_contains or []:
        tok = normalize_text(token)
        found = any(tok in hs for hs in source_haystacks)
        if not found:
            missing_source_tokens.append(token)

    sources_ok = len(missing_source_tokens) == 0

    best_rank = 9999
    expected_toks = [normalize_text(t) for t in expected_source_contains or []]
    if expected_toks:
        for i, hs in enumerate(source_haystacks, 1):
            if all(tok in hs for tok in expected_toks):
                best_rank = i
                break
    else:
        best_rank = 1

    mrr = 1.0 / best_rank if best_rank != 9999 else 0.0
    top_1 = (best_rank == 1)
    out_rank = None if best_rank == 9999 else best_rank

    # Conservative: ถ้า contexts ว่าง หรือ ไม่มี expected_source_contains และไม่มี context relevant ให้ retrieval_hit_pass=False
    # 1. contexts ว่างเปล่า (ไม่มี retrieval เลย) => retrieval_hit_pass = False
    # 2. expected_source_contains มี แต่ไม่มี context ไหน match เลย => retrieval_hit_pass = False
    # 3. expected_source_contains ว่าง แต่ contexts มีข้อมูล ให้ถือว่า retrieval_hit_pass = True เฉพาะถ้ามี context จริง
    if not contexts or len(contexts) == 0:
        return False, domain_ok, sources_ok, sorted(domain_set), missing_source_tokens, mrr, top_1, out_rank
    if expected_source_contains:
        if len(missing_source_tokens) == len(expected_source_contains):
            # ไม่มี context ไหน match expected_source_contains เลย
            return False, domain_ok, sources_ok, sorted(domain_set), missing_source_tokens, mrr, top_1, out_rank
    return domain_ok and domains_any_ok and sources_ok, domain_ok, sources_ok, sorted(domain_set), missing_source_tokens, mrr, top_1, out_rank


def citation_validity(answer: str, contexts: list[dict[str, Any]]) -> tuple[bool, int, int, list[str]]:
    citations = [(m.group(1).strip(), int(m.group(2))) for m in CITATION_RE.finditer(answer or "")]
    if not citations:
        return False, 0, 0, ["missing_citations"]

    context_entries: list[dict[str, Any]] = []
    for ctx in contexts or []:
        src = str((ctx or {}).get("source") or (ctx or {}).get("path") or "")
        pstart = (ctx or {}).get("page_start")
        pend = (ctx or {}).get("page_end")
        try:
            ps = int(pstart) if pstart is not None else None
        except Exception:
            ps = None
        try:
            pe = int(pend) if pend is not None else ps
        except Exception:
            pe = ps
        context_entries.append(
            {
                "source_token": normalize_source_token(src),
                "page_start": ps,
                "page_end": pe,
                "raw_source": src,
            }
        )

    valid_count = 0
    issues: list[str] = []
    for src, page in citations:
        src_tok = normalize_source_token(src)
        candidates = [e for e in context_entries if e["source_token"] == src_tok]
        if not candidates:
            issues.append(f"citation_source_not_found:{src}/{page}")
            continue

        match_page = False
        for c in candidates:
            ps = c["page_start"]
            pe = c["page_end"]
            if ps is None and pe is None:
                continue
            if ps is None:
                ps = pe
            if pe is None:
                pe = ps
            if ps is not None and pe is not None and ps <= page <= pe:
                match_page = True
                break

        if not match_page:
            issues.append(f"citation_page_not_found:{src}/{page}")
            continue

        valid_count += 1

    total = len(citations)
    return valid_count == total, total, valid_count, issues


def citation_source_precision_recall(
    answer: str,
    expected_source_contains: list[str],
) -> tuple[float | None, float | None, int, int, int]:
    citations = [(m.group(1).strip(), int(m.group(2))) for m in CITATION_RE.finditer(answer or "")]
    cited_sources: list[str] = []
    seen_cited: set[str] = set()
    for src, _ in citations:
        key = normalize_source_token(src)
        if not key or key in seen_cited:
            continue
        seen_cited.add(key)
        cited_sources.append(src)

    citation_source_tokens: set[str] = set()
    cited_source_variant_sets: list[set[str]] = []
    for src in cited_sources:
        variants = source_token_variants(src)
        if not variants:
            continue
        cited_source_variant_sets.append(variants)
        citation_source_tokens.update(variants)

    expected_tokens: set[str] = set()
    for token in (expected_source_contains or []):
        expected_tokens.update(source_token_variants(token))

    def _matched_predicted_sources() -> int:
        if not cited_source_variant_sets or not expected_tokens:
            return 0
        return sum(
            1
            for variants in cited_source_variant_sets
            if any(
                any(source_token_matches(v, exp) for exp in expected_tokens)
                for v in variants
            )
        )

    def _matched_expected_count() -> int:
        if not citation_source_tokens or not expected_tokens:
            return 0
        return sum(
            1
            for exp in expected_tokens
            if any(source_token_matches(exp, pred) for pred in citation_source_tokens)
        )

    matched_pred_sources = _matched_predicted_sources()
    matched_exp = _matched_expected_count()

    pred_sources_n = len(cited_source_variant_sets)

    if pred_sources_n == 0:
        precision = None
    else:
        precision = matched_pred_sources / pred_sources_n

    if not expected_tokens:
        recall = None
    else:
        recall = matched_exp / len(expected_tokens)

    # Use a bounded matched count for micro metrics so matched <= predicted and <= expected.
    matched_sources = min(matched_pred_sources, matched_exp)
    return precision, recall, pred_sources_n, len(expected_tokens), matched_sources


@dataclass
class CaseResult:
    id: str
    category: str
    question: str
    question_domain: str | None
    expected_source_contains: list[str]
    expected_answer_keywords: list[str]
    reference_answer: str | None
    expected_answerable: bool | None
    difficulty: str | None
    question_type: str | None
    expected_domain: str | None
    expected_domains_any: list[str]
    answer: str
    answer_hit_pass: bool
    answer_hit_coverage: float
    answer_keywords_matched: int
    answer_keywords_total: int
    retrieval_hit_pass: bool
    retrieval_domain_pass: bool
    retrieval_source_pass: bool
    retrieval_domains_found: list[str]
    retrieval_missing_source_tokens: list[str]
    retrieval_mrr: float
    retrieval_best_rank: int | None
    retrieval_top_1_pass: bool
    retrieval_top_3_pass: bool
    retrieval_top_5_pass: bool
    retrieval_top_contexts: list[dict[str, Any]]
    citation_validity_pass: bool
    citation_total: int
    citation_valid_count: int
    citation_issues: list[str]
    must_not_contain_pass: bool
    total_pass: bool
    total_latency_ms: float
    retrieval_latency_ms: float
    generation_latency_ms: float
    contexts_count: int
    error: str
    human_correctness_score: float | None
    human_completeness_score: float | None
    human_clarity_score: float | None
    human_hallucination: bool | None
    answerable_handled_correctly: bool | None
    quality_score_avg: float | None
    error_tags: list[str]
    adaptive: dict[str, Any]
    answer_schema: dict[str, Any]


def default_adaptive() -> dict[str, float]:
    return {
        "retrieval_adaptive_retry_triggered": 0.0,
        "retrieval_adaptive_retry_succeeded": 0.0,
        "retrieval_fallback_all_domains_triggered": 0.0,
        "retrieval_fallback_all_domains_succeeded": 0.0,
        "structured_rescue_triggered": 0.0,
        "structured_rescue_succeeded": 0.0,
        "curriculum_bypass_vector_triggered": 0.0,
        "low_confidence_detected": 0.0,
        "initial_retrieval_doc_count": 0.0,
        "retry_retrieval_doc_count": 0.0,
        "initial_top_score": 0.0,
        "retry_top_score": 0.0,
    }


def coerce_adaptive(meta: dict[str, Any]) -> dict[str, float]:
    out = default_adaptive()
    raw = (meta or {}).get("adaptive") if isinstance(meta, dict) else None
    if not isinstance(raw, dict):
        return out
    for k in out:
        try:
            out[k] = float(raw.get(k, out[k]))
        except Exception:
            out[k] = out[k]
    return out


def coerce_answer_schema(meta: dict[str, Any]) -> dict[str, Any]:
    raw = (meta or {}).get("answer_schema") if isinstance(meta, dict) else None
    if not isinstance(raw, dict):
        return {
            "task": "none",
            "repair_attempted": 0,
            "repair_success": 0,
            "missing_slots_before_count": 0,
            "missing_slots_after_count": 0,
        }

    task = str(raw.get("task") or "none").strip() or "none"
    def _to_int(v: Any) -> int:
        try:
            return int(v)
        except Exception:
            return 0

    return {
        "task": task,
        "repair_attempted": _to_int(raw.get("repair_attempted")),
        "repair_success": _to_int(raw.get("repair_success")),
        "missing_slots_before_count": _to_int(raw.get("missing_slots_before_count")),
        "missing_slots_after_count": _to_int(raw.get("missing_slots_after_count")),
    }


def summarize(results: list[CaseResult]) -> dict[str, Any]:
    total = len(results)
    lat_total = [r.total_latency_ms for r in results if r.total_latency_ms > 0]
    lat_ret = [r.retrieval_latency_ms for r in results if r.retrieval_latency_ms > 0]
    lat_gen = [r.generation_latency_ms for r in results if r.generation_latency_ms > 0]

    answer_hit_rate = sum(1 for r in results if r.answer_hit_pass) / total if total else 0.0
    retrieval_hit_rate = sum(1 for r in results if r.retrieval_hit_pass) / total if total else 0.0
    retrieval_mrr = statistics.mean([r.retrieval_mrr for r in results]) if total else 0.0
    retrieval_top_1_rate = sum(1 for r in results if r.retrieval_top_1_pass) / total if total else 0.0
    retrieval_top_3_rate = sum(1 for r in results if r.retrieval_top_3_pass) / total if total else 0.0
    retrieval_top_5_rate = sum(1 for r in results if r.retrieval_top_5_pass) / total if total else 0.0
    citation_validity_rate = sum(1 for r in results if r.citation_validity_pass) / total if total else 0.0
    citation_precision_rows: list[float] = []
    citation_recall_rows: list[float] = []
    citation_matched_sources_sum = 0
    citation_predicted_sources_sum = 0
    citation_expected_sources_sum = 0
    for r in results:
        c_prec, c_rec, pred_n, exp_n, matched_n = citation_source_precision_recall(
            r.answer,
            r.expected_source_contains,
        )
        if c_prec is not None:
            citation_precision_rows.append(float(c_prec))
        if c_rec is not None:
            citation_recall_rows.append(float(c_rec))
        citation_predicted_sources_sum += int(pred_n)
        citation_expected_sources_sum += int(exp_n)
        citation_matched_sources_sum += int(matched_n)
    citation_precision = clamp01(
        statistics.mean(citation_precision_rows) if citation_precision_rows else 0.0
    )
    citation_recall = clamp01(
        statistics.mean(citation_recall_rows) if citation_recall_rows else 0.0
    )
    citation_micro_precision = clamp01(
        (citation_matched_sources_sum / citation_predicted_sources_sum)
        if citation_predicted_sources_sum > 0
        else 0.0
    )
    citation_micro_recall = clamp01(
        (citation_matched_sources_sum / citation_expected_sources_sum)
        if citation_expected_sources_sum > 0
        else 0.0
    )
    must_not_pass_rate = sum(1 for r in results if r.must_not_contain_pass) / total if total else 0.0
    overall_pass_rate = sum(1 for r in results if r.total_pass) / total if total else 0.0

    # Quality metrics (prefer human labels when provided)
    quality_rows = [r for r in results if r.quality_score_avg is not None]
    quality_vals = [float(r.quality_score_avg) for r in quality_rows if r.quality_score_avg is not None]
    avg_quality_score = (
        statistics.mean(quality_vals) if quality_vals else 0.0
    )

    correctness_rows = [r for r in results if r.human_correctness_score is not None]
    pct_correct_answers = (
        sum(1 for r in correctness_rows if float(r.human_correctness_score or 0.0) >= 4.0) / len(correctness_rows)
        if correctness_rows
        else answer_hit_rate
    )

    hallucination_rows = [r for r in results if r.human_hallucination is not None]
    pct_hallucination = (
        sum(1 for r in hallucination_rows if r.human_hallucination is True) / len(hallucination_rows)
        if hallucination_rows
        else (1.0 - must_not_pass_rate)
    )

    answerable_rows = [r for r in results if r.answerable_handled_correctly is not None]
    pct_answerable_handled_correctly = (
        sum(1 for r in answerable_rows if r.answerable_handled_correctly) / len(answerable_rows)
        if answerable_rows
        else 0.0
    )

    # Coverage metrics
    coverage_by_domain: dict[str, int] = {}
    coverage_by_difficulty: dict[str, int] = {}
    coverage_by_question_type: dict[str, int] = {}
    for r in results:
        dom = r.question_domain or "unknown"
        coverage_by_domain[dom] = coverage_by_domain.get(dom, 0) + 1
        diff = r.difficulty or "unspecified"
        coverage_by_difficulty[diff] = coverage_by_difficulty.get(diff, 0) + 1
        qtype = r.question_type or "unspecified"
        coverage_by_question_type[qtype] = coverage_by_question_type.get(qtype, 0) + 1

    by_category: dict[str, dict[str, Any]] = {}
    by_domain: dict[str, dict[str, Any]] = {}
    for r in results:
        cat = r.category
        bucket = by_category.setdefault(
            cat,
            {
                "total": 0,
                "overall_pass": 0,
                "answer_hit_pass": 0,
                "retrieval_hit_pass": 0,
                "retrieval_top_1_pass": 0,
                "retrieval_top_3_pass": 0,
                "retrieval_top_5_pass": 0,
                "citation_validity_pass": 0,
                "retrieval_mrr_sum": 0.0,
            },
        )
        bucket["total"] += 1
        bucket["overall_pass"] += int(r.total_pass)
        bucket["answer_hit_pass"] += int(r.answer_hit_pass)
        bucket["retrieval_hit_pass"] += int(r.retrieval_hit_pass)
        bucket["retrieval_top_1_pass"] += int(r.retrieval_top_1_pass)
        bucket["retrieval_top_3_pass"] += int(r.retrieval_top_3_pass)
        bucket["retrieval_top_5_pass"] += int(r.retrieval_top_5_pass)
        bucket["retrieval_mrr_sum"] += r.retrieval_mrr
        bucket["citation_validity_pass"] += int(r.citation_validity_pass)

        dom = r.question_domain or "unknown"
        dom_bucket = by_domain.setdefault(
            dom,
            {
                "total": 0,
                "top1": 0,
                "top3": 0,
                "top5": 0,
                "mrr_sum": 0.0,
                "retrieval_hit": 0,
                "overall_pass": 0,
                "answer_hit": 0,
                "citation_validity": 0,
                "must_not_contain_pass": 0,
                "lat_total": [],
                "lat_retrieval": [],
                "lat_generation": [],
            },
        )
        dom_bucket["total"] += 1
        dom_bucket["top1"] += int(r.retrieval_top_1_pass)
        dom_bucket["top3"] += int(r.retrieval_top_3_pass)
        dom_bucket["top5"] += int(r.retrieval_top_5_pass)
        dom_bucket["mrr_sum"] += r.retrieval_mrr
        dom_bucket["retrieval_hit"] += int(r.retrieval_hit_pass)
        dom_bucket["overall_pass"] += int(r.total_pass)
        dom_bucket["answer_hit"] += int(r.answer_hit_pass)
        dom_bucket["citation_validity"] += int(r.citation_validity_pass)
        dom_bucket["must_not_contain_pass"] += int(r.must_not_contain_pass)
        dom_bucket["lat_total"].append(float(r.total_latency_ms))
        dom_bucket["lat_retrieval"].append(float(r.retrieval_latency_ms))
        dom_bucket["lat_generation"].append(float(r.generation_latency_ms))

    by_category_rates: dict[str, dict[str, float]] = {}
    for cat, m in by_category.items():
        n = max(1, int(m["total"]))
        by_category_rates[cat] = {
            "total": float(m["total"]),
            "overall_pass_rate": float(m["overall_pass"]) / n,
            "answer_hit_rate": float(m["answer_hit_pass"]) / n,
            "retrieval_hit_rate": float(m["retrieval_hit_pass"]) / n,
            "retrieval_top_1_rate": float(m["retrieval_top_1_pass"]) / n,
            "retrieval_top_3_rate": float(m["retrieval_top_3_pass"]) / n,
            "retrieval_top_5_rate": float(m["retrieval_top_5_pass"]) / n,
            "retrieval_mrr": float(m["retrieval_mrr_sum"]) / n,
            "citation_validity_rate": float(m["citation_validity_pass"]) / n,
        }

    by_domain_rates: dict[str, dict[str, float]] = {}
    for dom, m in by_domain.items():
        n = max(1, int(m["total"]))
        lat_total_dom = list(m.get("lat_total") or [])
        lat_ret_dom = list(m.get("lat_retrieval") or [])
        lat_gen_dom = list(m.get("lat_generation") or [])
        by_domain_rates[dom] = {
            "total": float(m["total"]),
            "overall_pass_rate": float(m["overall_pass"]) / n,
            "answer_hit_rate": float(m["answer_hit"]) / n,
            "retrieval_hit_rate": float(m["retrieval_hit"]) / n,
            "retrieval_top_1_rate": float(m["top1"]) / n,
            "retrieval_top_3_rate": float(m["top3"]) / n,
            "retrieval_top_5_rate": float(m["top5"]) / n,
            "retrieval_mrr": float(m["mrr_sum"]) / n,
            "citation_validity_rate": float(m["citation_validity"]) / n,
            "must_not_contain_pass_rate": float(m["must_not_contain_pass"]) / n,
            "avg_latency_ms": statistics.mean(lat_total_dom) if lat_total_dom else 0.0,
            "p95_latency_ms": percentile(lat_total_dom, 95),
            "avg_retrieval_latency_ms": statistics.mean(lat_ret_dom) if lat_ret_dom else 0.0,
            "p95_retrieval_latency_ms": percentile(lat_ret_dom, 95),
            "avg_generation_latency_ms": statistics.mean(lat_gen_dom) if lat_gen_dom else 0.0,
            "p95_generation_latency_ms": percentile(lat_gen_dom, 95),
        }

    adaptive_acc = default_adaptive()
    for r in results:
        for k in adaptive_acc:
            try:
                adaptive_acc[k] += float(r.adaptive.get(k, 0.0))
            except Exception:
                pass
    adaptive_avg = {
        k: (v / total if total else 0.0)
        for k, v in adaptive_acc.items()
    }

    answer_schema_by_task: dict[str, dict[str, float]] = {}
    for r in results:
        task = str((r.answer_schema or {}).get("task") or "none").strip() or "none"
        b = answer_schema_by_task.setdefault(
            task,
            {
                "cases": 0.0,
                "repair_attempted": 0.0,
                "repair_success": 0.0,
                "missing_slots_before_sum": 0.0,
                "missing_slots_after_sum": 0.0,
            },
        )
        b["cases"] += 1.0
        b["repair_attempted"] += float((r.answer_schema or {}).get("repair_attempted") or 0)
        b["repair_success"] += float((r.answer_schema or {}).get("repair_success") or 0)
        b["missing_slots_before_sum"] += float((r.answer_schema or {}).get("missing_slots_before_count") or 0)
        b["missing_slots_after_sum"] += float((r.answer_schema or {}).get("missing_slots_after_count") or 0)

    answer_schema_summary: dict[str, dict[str, float]] = {}
    for task, m in sorted(answer_schema_by_task.items()):
        cases_n = max(1.0, float(m["cases"]))
        attempted = float(m["repair_attempted"])
        success = float(m["repair_success"])
        answer_schema_summary[task] = {
            "cases": float(m["cases"]),
            "repair_attempted": attempted,
            "repair_success": success,
            "repair_attempt_rate": attempted / cases_n,
            "repair_success_rate_of_attempts": (success / attempted) if attempted > 0 else 0.0,
            "avg_missing_slots_before": float(m["missing_slots_before_sum"]) / cases_n,
            "avg_missing_slots_after": float(m["missing_slots_after_sum"]) / cases_n,
        }

    failures = [r for r in results if not r.total_pass]
    failures_sorted = sorted(
        failures,
        key=lambda x: (
            0 if x.error else 1,
            x.answer_hit_coverage,
            0 if x.citation_validity_pass else 1,
            x.total_latency_ms,
        ),
    )

    tag_counts: dict[str, int] = {}
    for r in results:
        for t in r.error_tags:
            tag_counts[t] = tag_counts.get(t, 0) + 1

    runtime_error_count = int(tag_counts.get("runtime_error", 0))
    runtime_error_rate = (float(runtime_error_count) / float(total)) if total else 0.0

    top_failed = []
    for f in failures_sorted[:20]:
        top_failed.append(
            {
                "id": f.id,
                "category": f.category,
                "domain": f.question_domain,
                "question": f.question,
                "error": f.error,
                "error_tags": f.error_tags,
                "answer_hit_coverage": f.answer_hit_coverage,
                "retrieval_hit_pass": f.retrieval_hit_pass,
                "citation_validity_pass": f.citation_validity_pass,
                "must_not_contain_pass": f.must_not_contain_pass,
                "total_latency_ms": f.total_latency_ms,
            }
        )

    return {
        "total_cases": total,
        "overall_pass_rate": overall_pass_rate,
        "answer_hit_rate": answer_hit_rate,
        "retrieval_hit_rate": retrieval_hit_rate,
        "retrieval_mrr": retrieval_mrr,
        "retrieval_top_1_rate": retrieval_top_1_rate,
        "retrieval_top_3_rate": retrieval_top_3_rate,
        "retrieval_top_5_rate": retrieval_top_5_rate,
        "citation_validity_rate": citation_validity_rate,
        "citation_precision": citation_precision,
        "citation_recall": citation_recall,
        "citation_micro_precision": citation_micro_precision,
        "citation_micro_recall": citation_micro_recall,
        "must_not_contain_pass_rate": must_not_pass_rate,
        "avg_quality_score": avg_quality_score,
        "pct_correct_answers": pct_correct_answers,
        "pct_hallucination": pct_hallucination,
        "pct_answerable_handled_correctly": pct_answerable_handled_correctly,
        "avg_latency_ms": statistics.mean(lat_total) if lat_total else 0.0,
        "median_latency_ms": statistics.median(lat_total) if lat_total else 0.0,
        "p95_latency_ms": percentile(lat_total, 95),
        "avg_retrieval_latency_ms": statistics.mean(lat_ret) if lat_ret else 0.0,
        "median_retrieval_latency_ms": statistics.median(lat_ret) if lat_ret else 0.0,
        "p95_retrieval_latency_ms": percentile(lat_ret, 95),
        "avg_generation_latency_ms": statistics.mean(lat_gen) if lat_gen else 0.0,
        "median_generation_latency_ms": statistics.median(lat_gen) if lat_gen else 0.0,
        "p95_generation_latency_ms": percentile(lat_gen, 95),
        "coverage": {
            "total_questions": total,
            "questions_by_domain": dict(sorted(coverage_by_domain.items())),
            "questions_by_difficulty": dict(sorted(coverage_by_difficulty.items())),
            "questions_by_question_type": dict(sorted(coverage_by_question_type.items())),
        },
        "by_category": by_category_rates,
        "by_domain": by_domain_rates,
        "adaptive_metrics_avg": adaptive_avg,
        "answer_schema_metrics_by_task": answer_schema_summary,
        "error_tag_counts": dict(sorted(tag_counts.items(), key=lambda kv: (-kv[1], kv[0]))),
        "runtime_error_count": runtime_error_count,
        "runtime_error_rate": runtime_error_rate,
        "failed_cases_top20": top_failed,
    }


def to_markdown(summary: dict[str, Any], input_path: Path, base_url: str) -> str:
    lines: list[str] = []
    lines.append("# Regression Eval Summary")
    lines.append("")
    lines.append(f"Generated: {datetime.now().isoformat()}")
    lines.append(f"Input: {input_path}")
    lines.append(f"Base URL: {base_url}")
    lines.append("")

    lines.append("## Headline")
    lines.append("")
    lines.append(f"- total cases: {summary['total_cases']}")
    lines.append(f"- overall pass rate: {summary['overall_pass_rate']:.4f}")
    lines.append("")
    lines.append("### Retrieval Metrics")
    lines.append(f"- top-1 hit rate: {summary['retrieval_top_1_rate']:.4f}")
    lines.append(f"- top-3 hit rate: {summary.get('retrieval_top_3_rate', 0.0):.4f}")
    lines.append(f"- top-5 hit rate: {summary.get('retrieval_top_5_rate', 0.0):.4f}")
    lines.append(f"- top-K hit rate: {summary.get('retrieval_hit_rate', 0.0):.4f}")
    lines.append(f"- mean reciprocal rank (mrr): {summary.get('retrieval_mrr', 0.0):.4f}")
    lines.append("")
    lines.append("### Answer Quality Metrics")
    lines.append(f"- answer keyword hit rate: {summary['answer_hit_rate']:.4f}")
    lines.append(f"- average quality score (1-5): {summary.get('avg_quality_score', 0.0):.4f}")
    lines.append(f"- % correct answers: {summary.get('pct_correct_answers', 0.0):.4f}")
    lines.append(f"- % hallucination: {summary.get('pct_hallucination', 0.0):.4f}")
    lines.append(f"- % answerable handled correctly: {summary.get('pct_answerable_handled_correctly', 0.0):.4f}")
    lines.append(f"- citation validity (groundedness): {summary['citation_validity_rate']:.4f}")
    lines.append(f"- citation precision: {summary.get('citation_precision', 0.0):.4f}")
    lines.append(f"- citation recall: {summary.get('citation_recall', 0.0):.4f}")
    lines.append(f"- citation micro precision: {summary.get('citation_micro_precision', 0.0):.4f}")
    lines.append(f"- citation micro recall: {summary.get('citation_micro_recall', 0.0):.4f}")
    lines.append(f"- must-not contain pass rate: {summary.get('must_not_contain_pass_rate', 0.0):.4f}")
    lines.append(f"- runtime error rate: {summary.get('runtime_error_rate', 0.0):.4f}")
    lines.append(f"- runtime error count: {int(summary.get('runtime_error_count', 0))}")
    lines.append("")
    lines.append("### Latency Metrics")
    lines.append(f"- avg total latency ms: {summary['avg_latency_ms']:.2f}")
    lines.append(f"- median total latency ms: {summary.get('median_latency_ms', 0.0):.2f}")
    lines.append(f"- p95 total latency ms: {summary['p95_latency_ms']:.2f}")
    lines.append(f"- avg retrieval latency ms: {summary['avg_retrieval_latency_ms']:.2f}")
    lines.append(f"- median retrieval latency ms: {summary.get('median_retrieval_latency_ms', 0.0):.2f}")
    lines.append(f"- p95 retrieval latency ms: {summary['p95_retrieval_latency_ms']:.2f}")
    lines.append(f"- avg generation latency ms: {summary.get('avg_generation_latency_ms', 0.0):.2f}")
    lines.append(f"- median generation latency ms: {summary.get('median_generation_latency_ms', 0.0):.2f}")
    lines.append(f"- p95 generation latency ms: {summary.get('p95_generation_latency_ms', 0.0):.2f}")
    lines.append("")

    lines.append("## Coverage")
    lines.append("")
    cov = summary.get("coverage") or {}
    lines.append(f"- total questions: {int(cov.get('total_questions', 0))}")
    for label, key in (
        ("questions by domain", "questions_by_domain"),
        ("questions by difficulty", "questions_by_difficulty"),
        ("questions by question type", "questions_by_question_type"),
    ):
        vals = cov.get(key) or {}
        if not vals:
            lines.append(f"- {label}: none")
            continue
        compact = ", ".join([f"{k}={v}" for k, v in sorted(vals.items())])
        lines.append(f"- {label}: {compact}")
    lines.append("")

    lines.append("## Retrieval By Domain")
    lines.append("")
    for dom in sorted((summary.get("by_domain") or {}).keys()):
        row = (summary.get("by_domain") or {}).get(dom) or {}
        lines.append(
            f"- {dom}: total={int(row.get('total', 0))}, top1={row.get('retrieval_top_1_rate', 0.0):.4f}, "
            f"top3={row.get('retrieval_top_3_rate', 0.0):.4f}, top5={row.get('retrieval_top_5_rate', 0.0):.4f}, "
            f"mrr={row.get('retrieval_mrr', 0.0):.4f}"
        )
    lines.append("")

    lines.append("## Domain Monitor")
    lines.append("")
    for dom in sorted((summary.get("by_domain") or {}).keys()):
        row = (summary.get("by_domain") or {}).get(dom) or {}
        lines.append(
            f"- {dom}: total={int(row.get('total', 0))}, overall={row.get('overall_pass_rate', 0.0):.4f}, "
            f"answer={row.get('answer_hit_rate', 0.0):.4f}, retrieval={row.get('retrieval_hit_rate', 0.0):.4f}, "
            f"citation={row.get('citation_validity_rate', 0.0):.4f}, "
            f"avg_latency_ms={row.get('avg_latency_ms', 0.0):.2f}, p95_latency_ms={row.get('p95_latency_ms', 0.0):.2f}"
        )
    lines.append("")

    lines.append("## By Category")
    lines.append("")
    for cat in sorted(summary["by_category"].keys()):
        row = summary["by_category"][cat]
        lines.append(
            f"- {cat}: total={int(row['total'])}, overall={row['overall_pass_rate']:.4f}, "
            f"answer={row['answer_hit_rate']:.4f}, retrieval={row['retrieval_hit_rate']:.4f}, "
            f"top1={row.get('retrieval_top_1_rate', 0.0):.4f}, top3={row.get('retrieval_top_3_rate', 0.0):.4f}, "
            f"top5={row.get('retrieval_top_5_rate', 0.0):.4f}, "
            f"citation={row['citation_validity_rate']:.4f}"
        )
    lines.append("")

    lines.append("## Error Tag Counts")
    lines.append("")
    tag_counts = summary.get("error_tag_counts") or {}
    if not tag_counts:
        lines.append("- none")
    else:
        for tag, cnt in tag_counts.items():
            lines.append(f"- {tag}: {cnt}")
    lines.append("")

    lines.append("## Adaptive Metrics")
    lines.append("")
    for k, v in summary["adaptive_metrics_avg"].items():
        lines.append(f"- {k}: {v:.4f}")
    lines.append("")

    lines.append("## Answer Schema Metrics By Task")
    lines.append("")
    asm = summary.get("answer_schema_metrics_by_task") or {}
    if not asm:
        lines.append("- none")
    else:
        for task, row in sorted(asm.items()):
            lines.append(
                f"- {task}: cases={int(row.get('cases', 0))}, attempted={int(row.get('repair_attempted', 0))}, "
                f"success={int(row.get('repair_success', 0))}, attempt_rate={row.get('repair_attempt_rate', 0.0):.4f}, "
                f"success_rate_of_attempts={row.get('repair_success_rate_of_attempts', 0.0):.4f}, "
                f"avg_missing_before={row.get('avg_missing_slots_before', 0.0):.4f}, "
                f"avg_missing_after={row.get('avg_missing_slots_after', 0.0):.4f}"
            )
    lines.append("")

    lines.append("## Failed Cases Top 20")
    lines.append("")
    top_failed = summary.get("failed_cases_top20") or []
    if not top_failed:
        lines.append("- none")
    else:
        for f in top_failed:
            lines.append(
                f"- {f['id']} ({f['category']}): coverage={f['answer_hit_coverage']:.2f}, "
                f"retrieval={f['retrieval_hit_pass']}, citation={f['citation_validity_pass']}, "
                f"must_not={f['must_not_contain_pass']}, latency_ms={f['total_latency_ms']:.1f}, "
                f"tags={','.join(f.get('error_tags') or [])}, error={f['error'] or 'none'}"
            )
    lines.append("")

    return "\n".join(lines)


def build_baseline(summary: dict[str, Any], commit_sha: str) -> dict[str, Any]:
    by_cat = summary.get("by_category") or {}
    adaptive = summary.get("adaptive_metrics_avg") or {}
    return {
        "commit": commit_sha,
        "overall_pass_rate": summary.get("overall_pass_rate", 0.0),
        "per_category_pass_rate": {
            k: (v.get("overall_pass_rate", 0.0) if isinstance(v, dict) else 0.0)
            for k, v in by_cat.items()
        },
        "citation_validity_rate": summary.get("citation_validity_rate", 0.0),
        "avg_latency_ms": summary.get("avg_latency_ms", 0.0),
        "p95_latency_ms": summary.get("p95_latency_ms", 0.0),
        "adaptive_retry_rate": adaptive.get("retrieval_adaptive_retry_triggered", 0.0),
        "fallback_rate": adaptive.get("retrieval_fallback_all_domains_triggered", 0.0),
        "structured_rescue_rate": adaptive.get("structured_rescue_triggered", 0.0),
    }


def baseline_markdown(baseline: dict[str, Any]) -> str:
    lines = ["# Baseline Snapshot", ""]
    for k, v in baseline.items():
        if isinstance(v, dict):
            lines.append(f"- {k}:")
            for sk, sv in sorted(v.items()):
                lines.append(f"  - {sk}: {sv}")
        else:
            lines.append(f"- {k}: {v}")
    lines.append("")
    return "\n".join(lines)


def apply_gate(
    summary: dict[str, Any],
    baseline: dict[str, Any],
    *,
    overall_drop_pct: float,
    citation_drop_pct: float,
    p95_increase_pct: float,
    protected_categories: list[str],
) -> list[str]:
    failures: list[str] = []

    current_overall = float(summary.get("overall_pass_rate", 0.0))
    base_overall = float(baseline.get("overall_pass_rate", 0.0))
    if current_overall < (base_overall - (overall_drop_pct / 100.0)):
        failures.append(
            f"overall pass rate dropped too much: current={current_overall:.4f}, baseline={base_overall:.4f}, allowed_drop={overall_drop_pct:.2f}%"
        )

    current_citation = float(summary.get("citation_validity_rate", 0.0))
    base_citation = float(baseline.get("citation_validity_rate", 0.0))
    if current_citation < (base_citation - (citation_drop_pct / 100.0)):
        failures.append(
            f"citation validity dropped: current={current_citation:.4f}, baseline={base_citation:.4f}, allowed_drop={citation_drop_pct:.2f}%"
        )

    current_p95 = float(summary.get("p95_latency_ms", 0.0))
    base_p95 = float(baseline.get("p95_latency_ms", 0.0))
    allowed_p95 = base_p95 * (1.0 + p95_increase_pct / 100.0)
    if base_p95 > 0 and current_p95 > allowed_p95:
        failures.append(
            f"p95 latency exceeded threshold: current={current_p95:.2f} ms, baseline={base_p95:.2f} ms, allowed={allowed_p95:.2f} ms"
        )

    current_cat = summary.get("by_category") or {}
    base_cat = baseline.get("per_category_pass_rate") or {}
    for cat in protected_categories:
        cur = float(((current_cat.get(cat) or {}).get("overall_pass_rate", 0.0)))
        base = float(base_cat.get(cat, 0.0))
        if cur < base:
            failures.append(
                f"protected category dropped: {cat} current={cur:.4f}, baseline={base:.4f}"
            )

    return failures


def apply_production_gate(
    summary: dict[str, Any],
    *,
    min_overall_pass_rate: float,
    min_answer_hit_rate: float,
    min_retrieval_hit_rate: float,
    min_citation_validity_rate: float,
    min_citation_precision: float,
    min_citation_recall: float,
    max_hallucination_rate: float,
    min_must_not_contain_pass_rate: float,
    max_p95_latency_ms: float,
    max_p95_retrieval_latency_ms: float,
    category_min_overall_pass_rate: dict[str, float],
    domain_min_overall_pass_rate: dict[str, float],
    domain_max_p95_latency_ms: dict[str, float],
) -> list[str]:
    failures: list[str] = []

    def _check_min(metric_key: str, threshold: float, label: str) -> None:
        cur = float(summary.get(metric_key, 0.0))
        if cur < float(threshold):
            failures.append(
                f"{label} below production threshold: current={cur:.4f}, threshold={float(threshold):.4f}"
            )

    _check_min("overall_pass_rate", min_overall_pass_rate, "overall pass rate")
    _check_min("answer_hit_rate", min_answer_hit_rate, "answer hit rate")
    _check_min("retrieval_hit_rate", min_retrieval_hit_rate, "retrieval hit rate")
    _check_min("citation_validity_rate", min_citation_validity_rate, "citation validity rate")
    _check_min("citation_precision", min_citation_precision, "citation precision")
    _check_min("citation_recall", min_citation_recall, "citation recall")
    _check_min("must_not_contain_pass_rate", min_must_not_contain_pass_rate, "must-not-contain pass rate")

    cur_hallucination = float(summary.get("pct_hallucination", 0.0))
    if cur_hallucination > float(max_hallucination_rate):
        failures.append(
            f"hallucination rate above production threshold: current={cur_hallucination:.4f}, threshold={float(max_hallucination_rate):.4f}"
        )

    cur_p95 = float(summary.get("p95_latency_ms", 0.0))
    if cur_p95 > float(max_p95_latency_ms):
        failures.append(
            f"p95 total latency above production threshold: current={cur_p95:.2f} ms, threshold={float(max_p95_latency_ms):.2f} ms"
        )

    cur_p95_ret = float(summary.get("p95_retrieval_latency_ms", 0.0))
    if cur_p95_ret > float(max_p95_retrieval_latency_ms):
        failures.append(
            f"p95 retrieval latency above production threshold: current={cur_p95_ret:.2f} ms, threshold={float(max_p95_retrieval_latency_ms):.2f} ms"
        )

    by_cat = summary.get("by_category") or {}
    for cat, threshold in sorted((category_min_overall_pass_rate or {}).items()):
        cur = float(((by_cat.get(cat) or {}).get("overall_pass_rate", 0.0)))
        if cur < float(threshold):
            failures.append(
                f"category overall pass rate below production threshold: {cat} current={cur:.4f}, threshold={float(threshold):.4f}"
            )

    by_dom = summary.get("by_domain") or {}
    for dom, threshold in sorted((domain_min_overall_pass_rate or {}).items()):
        cur = float(((by_dom.get(dom) or {}).get("overall_pass_rate", 0.0)))
        if cur < float(threshold):
            failures.append(
                f"domain overall pass rate below production threshold: {dom} current={cur:.4f}, threshold={float(threshold):.4f}"
            )

    for dom, threshold in sorted((domain_max_p95_latency_ms or {}).items()):
        cur = float(((by_dom.get(dom) or {}).get("p95_latency_ms", 0.0)))
        if cur > float(threshold):
            failures.append(
                f"domain p95 latency above production threshold: {dom} current={cur:.2f} ms, threshold={float(threshold):.2f} ms"
            )

    return failures


def main() -> int:
    ap = argparse.ArgumentParser(description="Persistent regression evaluator for RAG")
    ap.add_argument("--input", default="eval_cases.json")
    ap.add_argument("--base-url", default="http://127.0.0.1:8001")
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument("--preflight-health", action="store_true", help="Check /health before running eval")
    ap.add_argument("--preflight-retries", type=int, default=5)
    ap.add_argument("--preflight-interval-s", type=float, default=2.0)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--output-prefix", default="")
    ap.add_argument("--baseline-commit", default="")
    ap.add_argument("--compare-baseline", default="")
    ap.add_argument("--gate-overall-drop-pct", type=float, default=3.0)
    ap.add_argument("--gate-citation-drop-pct", type=float, default=0.0)
    ap.add_argument("--gate-p95-increase-pct", type=float, default=25.0)
    ap.add_argument(
        "--gate-protected-categories",
        default="curriculum_fact_lookup,regulations",
    )
    ap.add_argument("--production-gate", action="store_true", help="Enable absolute production gate thresholds")
    ap.add_argument("--prod-min-overall-pass-rate", type=float, default=0.80)
    ap.add_argument("--prod-min-answer-hit-rate", type=float, default=0.80)
    ap.add_argument("--prod-min-retrieval-hit-rate", type=float, default=0.85)
    ap.add_argument("--prod-min-citation-validity-rate", type=float, default=0.95)
    ap.add_argument("--prod-min-citation-precision", type=float, default=0.0)
    ap.add_argument("--prod-min-citation-recall", type=float, default=0.0)
    ap.add_argument("--prod-max-hallucination-rate", type=float, default=1.0)
    ap.add_argument("--prod-min-must-not-contain-pass-rate", type=float, default=0.98)
    ap.add_argument("--prod-max-p95-latency-ms", type=float, default=7000.0)
    ap.add_argument("--prod-max-p95-retrieval-latency-ms", type=float, default=2500.0)
    ap.add_argument(
        "--prod-category-min-overall-pass-rate",
        default=",".join(f"{k}={v}" for k, v in DEFAULT_PRODUCTION_CATEGORY_MIN_OVERALL.items()),
        help="Comma-separated category threshold map, e.g. regulations=0.9,curriculum_fact_lookup=0.9",
    )
    ap.add_argument(
        "--prod-domain-min-overall-pass-rate",
        default="",
        help="Comma-separated domain threshold map, e.g. announcements=0.8,regulations=0.4",
    )
    ap.add_argument(
        "--prod-domain-max-p95-latency-ms",
        default=",".join(f"{k}={v}" for k, v in DEFAULT_PRODUCTION_DOMAIN_MAX_P95_LATENCY_MS.items()),
        help="Comma-separated domain p95 latency limits in ms, e.g. announcements=1400,regulations=2500",
    )
    ap.add_argument(
        "--max-runtime-error-rate",
        type=float,
        default=0.05,
        help="Maximum allowed runtime error ratio before marking infra failure",
    )
    args = ap.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Input not found: {input_path}", file=sys.stderr)
        return 2

    cases = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(cases, list):
        print("Input must be a JSON array", file=sys.stderr)
        return 2

    if args.preflight_health:
        ok, preflight_err = preflight_healthcheck(
            args.base_url,
            timeout_s=float(args.timeout),
            retries=int(args.preflight_retries),
            interval_s=float(args.preflight_interval_s),
        )
        if not ok:
            print(
                f"INFRA PRECHECK FAILED: base_url={args.base_url} err={preflight_err}",
                file=sys.stderr,
                flush=True,
            )
            return 4

    results: list[CaseResult] = []
    total = 0
    planned_cases = sort_cases_for_execution([c for c in cases if isinstance(c, dict)])
    if args.limit:
        planned_cases = planned_cases[: int(args.limit)]
    planned_total = len(planned_cases)
    conversation_histories: dict[str, list[dict[str, str]]] = {}

    print(
        f"[heartbeat] start total_cases={planned_total} base_url={args.base_url} timeout_s={float(args.timeout):.1f}",
        flush=True,
    )

    for case in planned_cases:
        if args.limit and total >= int(args.limit):
            break

        total += 1

        cid = str(case.get("id") or f"case_{total:03d}")
        category = str(case.get("category") or "uncategorized")
        question = str(case.get("question") or "").strip()
        expected_domain_raw = str(case.get("expected_domain") or "").strip().lower()
        expected_domain = expected_domain_raw if expected_domain_raw else None
        expected_domains_any = [
            str(x).strip().lower()
            for x in (case.get("expected_domains_any") or [])
            if str(x).strip()
        ]
        conversation_id = case_conversation_id(case)
        retrieval_payload, answer_payload, payload_session_id = build_eval_request_payloads(
            case,
            conversation_histories.get(conversation_id, []),
        )

        case_t0 = time.perf_counter()
        print(
            f"[heartbeat] case_start idx={total}/{planned_total or total} id={cid} category={category} domain={expected_domain or 'auto'} session={payload_session_id or 'none'}",
            flush=True,
        )

        retrieval_data, retrieval_ms, retrieval_err = post_json(
            args.base_url, "/rag/query", retrieval_payload, timeout_s=float(args.timeout)
        )
        answer_data, total_ms, answer_err = post_json(
            args.base_url, "/rag/answer", answer_payload, timeout_s=float(args.timeout)
        )
        # /rag/query can include extra exploratory retries that do not represent the
        # serving path used by /rag/answer. Cap retrieval latency to end-to-end answer
        # latency to prevent inflated p95 retrieval gate decisions.
        retrieval_ms = min(float(retrieval_ms), float(total_ms))

        answer = str(answer_data.get("answer") or "").strip()

        if conversation_id:
            history = list(conversation_histories.get(conversation_id) or [])
            history.append({"role": "user", "content": question})
            history.append({"role": "assistant", "content": answer})
            conversation_histories[conversation_id] = history[-12:]

        retrieval_contexts = retrieval_data.get("contexts") or []
        answer_contexts = answer_data.get("contexts") or []
        contexts = answer_contexts if answer_contexts else retrieval_contexts

        answer_matched, answer_total, answer_coverage, answer_pass = answer_keyword_stats(
            answer,
            list(case.get("expected_answer_keywords") or []),
        )

        retrieval_pass, retrieval_domain_pass, retrieval_source_pass, domains_found, missing_source, mrr, top1, best_rank = retrieval_hit(
            contexts,
            expected_domain,
            expected_domains_any,
            list(case.get("expected_source_contains") or []),
        )
        top3 = best_rank is not None and best_rank <= 3
        top5 = best_rank is not None and best_rank <= 5

        citation_pass, citation_total, citation_valid, citation_issues = citation_validity(answer, contexts)
        must_not_pass = must_not_contain_ok(answer, list(case.get("must_not_contain") or []))

        expected_answerable = to_bool_or_none(case.get("expected_answerable"))
        abstained = detect_system_abstain(answer)
        answerable_handled: bool | None = None
        if expected_answerable is True:
            has_keywords = bool(list(case.get("expected_answer_keywords") or []))
            answerable_handled = bool((answer_pass if has_keywords else (not abstained)) and not answer_err)
        elif expected_answerable is False:
            answerable_handled = bool(abstained and not answer_err)

        h_correct = case.get("human_correctness_score")
        h_complete = case.get("human_completeness_score")
        h_clarity = case.get("human_clarity_score")
        try:
            h_correct_f = float(h_correct) if h_correct is not None else None
        except Exception:
            h_correct_f = None
        try:
            h_complete_f = float(h_complete) if h_complete is not None else None
        except Exception:
            h_complete_f = None
        try:
            h_clarity_f = float(h_clarity) if h_clarity is not None else None
        except Exception:
            h_clarity_f = None

        quality_parts = [x for x in [h_correct_f, h_complete_f, h_clarity_f] if x is not None]
        quality_avg = statistics.mean(quality_parts) if quality_parts else None
        human_hallu = to_bool_or_none(case.get("human_hallucination"))

        err = answer_err or retrieval_err
        total_pass = bool(answer_pass and retrieval_pass and citation_pass and must_not_pass and not err)

        meta = answer_data.get("meta") if isinstance(answer_data, dict) else None
        if not isinstance(meta, dict):
            meta = retrieval_data.get("meta") if isinstance(retrieval_data, dict) else {}
        adaptive = coerce_adaptive(meta or {})
        answer_schema = coerce_answer_schema(meta or {})

        q_domain = first_non_empty_str(
            case.get("domain"),
            expected_domain,
            (domains_found[0] if domains_found else ""),
        ).lower() or None

        generation_ms = max(0.0, float(total_ms) - float(retrieval_ms))
        error_tags = case_error_tags(
            error=err,
            retrieval_hit_pass=retrieval_pass,
            retrieval_domain_pass=retrieval_domain_pass,
            retrieval_source_pass=retrieval_source_pass,
            answer_hit_pass=answer_pass,
            citation_validity_pass=citation_pass,
            must_not_contain_pass=must_not_pass,
            human_hallucination=human_hallu,
        )

        results.append(
            CaseResult(
                id=cid,
                category=category,
                question=question,
                question_domain=q_domain,
                expected_source_contains=list(case.get("expected_source_contains") or []),
                expected_answer_keywords=list(case.get("expected_answer_keywords") or []),
                reference_answer=(str(case.get("reference_answer") or "").strip() or None),
                expected_answerable=expected_answerable,
                difficulty=(str(case.get("difficulty") or "").strip().lower() or None),
                question_type=(str(case.get("question_type") or case.get("reasoning_type") or "").strip().lower() or None),
                expected_domain=expected_domain,
                expected_domains_any=expected_domains_any,
                answer=answer,
                answer_hit_pass=answer_pass,
                answer_hit_coverage=answer_coverage,
                answer_keywords_matched=answer_matched,
                answer_keywords_total=answer_total,
                retrieval_hit_pass=retrieval_pass,
                retrieval_domain_pass=retrieval_domain_pass,
                retrieval_source_pass=retrieval_source_pass,
                retrieval_domains_found=domains_found,
                retrieval_missing_source_tokens=missing_source,
                retrieval_mrr=mrr,
                retrieval_best_rank=best_rank,
                retrieval_top_1_pass=top1,
                retrieval_top_3_pass=top3,
                retrieval_top_5_pass=top5,
                retrieval_top_contexts=top_context_rows(contexts, k=5),
                citation_validity_pass=citation_pass,
                citation_total=citation_total,
                citation_valid_count=citation_valid,
                citation_issues=citation_issues,
                must_not_contain_pass=must_not_pass,
                total_pass=total_pass,
                total_latency_ms=total_ms,
                retrieval_latency_ms=retrieval_ms,
                generation_latency_ms=generation_ms,
                contexts_count=len(contexts or []),
                error=err,
                human_correctness_score=h_correct_f,
                human_completeness_score=h_complete_f,
                human_clarity_score=h_clarity_f,
                human_hallucination=human_hallu,
                answerable_handled_correctly=answerable_handled,
                quality_score_avg=quality_avg,
                error_tags=error_tags,
                adaptive=adaptive,
                answer_schema=answer_schema,
            )
        )

        case_ms = (time.perf_counter() - case_t0) * 1000.0
        print(
            (
                f"[heartbeat] case_done idx={total}/{planned_total or total} id={cid} "
                f"pass={int(total_pass)} err={int(bool(err))} "
                f"latency_ms={total_ms:.1f} case_ms={case_ms:.1f}"
            ),
            flush=True,
        )

    summary = summarize(results)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    if args.output_prefix:
        out_json = Path(f"{args.output_prefix}.json")
        out_md = Path(f"{args.output_prefix}.md")
    else:
        out_json = Path("reports") / f"eval_runner_{ts}.json"
        out_md = Path("reports") / f"eval_runner_{ts}.md"

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "summary": summary,
        "cases": [asdict(r) for r in results],
    }
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    out_md.write_text(to_markdown(summary, input_path, args.base_url), encoding="utf-8")

    print(f"Wrote JSON: {out_json}", flush=True)
    print(f"Wrote MD:   {out_md}", flush=True)

    runtime_error_rate = float(summary.get("runtime_error_rate", 0.0))
    if runtime_error_rate > float(args.max_runtime_error_rate):
        print(
            (
                "INFRA FAILURE: runtime_error_rate exceeded threshold "
                f"current={runtime_error_rate:.4f} threshold={float(args.max_runtime_error_rate):.4f}"
            ),
            file=sys.stderr,
            flush=True,
        )
        return 4

    if args.baseline_commit:
        short = (args.baseline_commit or "").strip()[:7]
        baseline = build_baseline(summary, args.baseline_commit)
        b_json = Path("reports") / f"baseline_{short}.json"
        b_md = Path("reports") / f"baseline_{short}.md"
        b_json.write_text(json.dumps(baseline, ensure_ascii=False, indent=2), encoding="utf-8")
        b_md.write_text(baseline_markdown(baseline), encoding="utf-8")
        print(f"Wrote baseline JSON: {b_json}", flush=True)
        print(f"Wrote baseline MD:   {b_md}", flush=True)

    gate_failures: list[str] = []

    if args.compare_baseline:
        baseline_path = Path(args.compare_baseline)
        if not baseline_path.exists():
            print(f"Baseline file not found: {baseline_path}", file=sys.stderr)
            return 3

        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        protected = [
            x.strip()
            for x in str(args.gate_protected_categories).split(",")
            if x.strip()
        ]
        baseline_gate_failures = apply_gate(
            summary,
            baseline,
            overall_drop_pct=float(args.gate_overall_drop_pct),
            citation_drop_pct=float(args.gate_citation_drop_pct),
            p95_increase_pct=float(args.gate_p95_increase_pct),
            protected_categories=protected,
        )
        gate_failures.extend(baseline_gate_failures)
        if baseline_gate_failures:
            print("GATE FAILED", flush=True)
            for line in baseline_gate_failures:
                print(f"- {line}", flush=True)
        else:
            print("GATE PASSED", flush=True)

    if args.production_gate:
        prod_cat_thresholds = parse_category_thresholds(args.prod_category_min_overall_pass_rate)
        prod_dom_min_thresholds = parse_category_thresholds(args.prod_domain_min_overall_pass_rate)
        prod_dom_p95_thresholds = parse_category_thresholds(args.prod_domain_max_p95_latency_ms)
        prod_gate_failures = apply_production_gate(
            summary,
            min_overall_pass_rate=float(args.prod_min_overall_pass_rate),
            min_answer_hit_rate=float(args.prod_min_answer_hit_rate),
            min_retrieval_hit_rate=float(args.prod_min_retrieval_hit_rate),
            min_citation_validity_rate=float(args.prod_min_citation_validity_rate),
            min_citation_precision=float(args.prod_min_citation_precision),
            min_citation_recall=float(args.prod_min_citation_recall),
            max_hallucination_rate=float(args.prod_max_hallucination_rate),
            min_must_not_contain_pass_rate=float(args.prod_min_must_not_contain_pass_rate),
            max_p95_latency_ms=float(args.prod_max_p95_latency_ms),
            max_p95_retrieval_latency_ms=float(args.prod_max_p95_retrieval_latency_ms),
            category_min_overall_pass_rate=prod_cat_thresholds,
            domain_min_overall_pass_rate=prod_dom_min_thresholds,
            domain_max_p95_latency_ms=prod_dom_p95_thresholds,
        )
        gate_failures.extend(prod_gate_failures)
        if prod_gate_failures:
            print("PRODUCTION GATE FAILED", flush=True)
            for line in prod_gate_failures:
                print(f"- {line}", flush=True)
        else:
            print("PRODUCTION GATE PASSED", flush=True)

    if gate_failures:
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
