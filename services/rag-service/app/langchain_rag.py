import os
import json
import re
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
from typing import Any, Dict, Optional, List, Tuple

from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda

from .rag_logic import (
    normalize_question,
    search_query_from_question,
    infer_domain,
    retrieve_by_domain,
    retrieve_all_domains,
    pack_context,
    build_prompt,
    est_tokens,
)
from .config import RRF_K, MAX_CONTEXTS
from .llm import llm_engine
from .chroma_client import embed_texts


_SYSTEM_MSG: dict[str, str] = {
    'role': 'system',
    'content': (
        'คุณคือผู้ช่วยของภาควิชาวิศวกรรมคอมพิวเตอร์ '
        'ใช้เฉพาะข้อมูลในบริบทเท่านั้น ตอบโดยตรงและชัดเจน '
        'ห้ามให้ลิงก์/URL ภายนอก เว้นแต่ปรากฏอยู่ในบริบท '
        'หากคำถามกำกวมให้ถามกลับ 1 คำถามสั้น ๆ เพื่อขอรายละเอียดที่จำเป็น '
        'หากไม่พบคำตอบแบบชัดเจน ให้สรุปเท่าที่สรุปได้จากบริบท และระบุว่าเอกสารไม่ได้กล่าวตรง ๆ '
        'หรือไม่มีข้อความยืนยันโดยตรง'
    ),
}

_MULTIQUERY_ENABLE = os.getenv('RAG_LC_MULTIQUERY', '0') in ('1', 'true', 'True')
_MULTIQUERY_N = int(os.getenv('RAG_LC_MULTIQUERY_N', '3') or '3')
_MULTIQUERY_ALL = os.getenv('RAG_LC_MULTIQUERY_ALL', '0') in ('1', 'true', 'True')

_PARALLEL_ENABLE = os.getenv('RAG_LC_PARALLEL', '0') in ('1', 'true', 'True')
_PARALLEL_WORKERS = int(os.getenv('RAG_LC_PARALLEL_WORKERS', '4') or '4')

_RERANK_ENABLE = os.getenv('RAG_LC_RERANK', '0') in ('1', 'true', 'True')
_RERANK_TOPN = int(os.getenv('RAG_LC_RERANK_TOPN', '24') or '24')
_RERANK_ALL = os.getenv('RAG_LC_RERANK_ALL', '0') in ('1', 'true', 'True')

_COMPRESS_ENABLE = os.getenv('RAG_LC_COMPRESS', '0') in ('1', 'true', 'True')
_COMPRESS_MAX_CHARS = int(os.getenv('RAG_LC_COMPRESS_MAX_CHARS', '700') or '700')
_COMPRESS_ALL = os.getenv('RAG_LC_COMPRESS_ALL', '0') in ('1', 'true', 'True')

_ROUTE_LLM_ENABLE = os.getenv('RAG_LC_ROUTE_LLM', '0') in ('1', 'true', 'True')

_STRUCTURED_ENABLE = os.getenv('RAG_LC_STRUCTURED', '0') in ('1', 'true', 'True')

_ENFORCE_CITATIONS = os.getenv('RAG_LC_ENFORCE_CITATIONS', '0') in ('1', 'true', 'True')


def _extract_citations_from_text(answer: str) -> List[str]:
    cites: List[str] = []
    for m in re.finditer(r"\[([^\[\]]+?)\]", answer or ''):
        c = (m.group(1) or '').strip()
        if c:
            cites.append(c)
    return cites


def _ensure_bullet_has_cite(line: str, fallback_cite: str) -> str:
    s = (line or '').rstrip()
    if not s.strip().startswith('- '):
        return s
    # If the line already contains at least one [..] citation, keep as-is.
    if re.search(r"\[[^\[\]]+\]", s):
        return s
    if not fallback_cite:
        return s
    return f"{s} [{fallback_cite}]"


def _enforce_citations(answer: str, allowed_cites: List[str]) -> str:
    if not answer or not allowed_cites:
        return answer
    fallback = (allowed_cites[0] or '').strip()
    if not fallback:
        return answer
    lines = (answer or '').splitlines()
    out_lines: List[str] = []
    for ln in lines:
        out_lines.append(_ensure_bullet_has_cite(ln, fallback))
    return "\n".join(out_lines).strip()


def _parse_query_list(raw: str) -> List[str]:
    """Parse LLM output into a compact list of query strings."""
    txt = (raw or '').strip()
    if not txt:
        return []

    # Try JSON array first.
    try:
        # Some models wrap JSON in extra text; try to extract the first [...] block.
        m = re.search(r"\[[\s\S]*\]", txt)
        candidate = m.group(0) if m else txt
        data = json.loads(candidate)
        if isinstance(data, list):
            out: List[str] = []
            for x in data:
                if isinstance(x, str) and x.strip():
                    out.append(x.strip())
            return out
    except Exception:
        pass

    # Fallback: lines like "- ..." or "1) ..."
    items: List[str] = []
    for ln in txt.splitlines():
        s = (ln or '').strip()
        if not s:
            continue
        s = re.sub(r"^[-•\*]+\s+", "", s)
        s = re.sub(r"^\d+[\.)]\s+", "", s)
        if s:
            items.append(s)
    return items


def _dedupe_keep_order(items: List[str], cap: int) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for it in items:
        s = (it or '').strip()
        if not s:
            continue
        key = s.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
        if len(out) >= cap:
            break
    return out


def _multiquery_variants(question_display: str, base_query: str, domain: str | None) -> List[str]:
    """Generate retrieval queries (best-effort).

    If LLM is disabled/unavailable, returns [] and the caller should fall back.
    """
    if not _MULTIQUERY_ENABLE:
        return []
    n = max(0, min(6, int(_MULTIQUERY_N)))
    if n <= 0:
        return []

    dom = (domain or '').strip().lower() or 'auto'
    prompt = (
        "สร้างคำค้น (search query) ทางเลือกเพื่อค้นหาเอกสารที่เกี่ยวข้องกับคำถามนี้ ให้มีความหลากหลายแต่ยังเกี่ยวข้อง\n"
        f"คำถาม: {question_display}\n"
        f"คำค้นตั้งต้น: {base_query}\n"
        f"โดเมน (ถ้าทราบ): {dom}\n\n"
        f"ขอ {n} คำค้นใหม่ โดย:\n"
        "- ต้องสั้น กระชับ เหมาะกับค้นหาในเอกสาร\n"
        "- คงคำสำคัญ (เช่น รหัสวิชา, ปี พ.ศ., คำเฉพาะ)\n"
        "- อนุญาตให้เติมคำอังกฤษในวงเล็บเพื่อช่วย recall ได้\n\n"
        "ตอบกลับเป็น JSON array ของ string เท่านั้น เช่น [\"...\", \"...\"]"
    )

    raw = llm_engine.generate(prompt)
    if not raw or raw.strip().startswith('('):
        return []
    candidates = _parse_query_list(raw)
    # Clean: drop extremely long lines
    candidates = [c for c in candidates if 2 <= len(c) <= 180]
    return _dedupe_keep_order(candidates, cap=n)


def _safe_json_obj(raw: str) -> Optional[Dict[str, Any]]:
    txt = (raw or '').strip()
    if not txt:
        return None
    # Try to extract the first {...} block if the model wrapped it.
    try:
        m = re.search(r"\{[\s\S]*\}", txt)
        candidate = m.group(0) if m else txt
        data = json.loads(candidate)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _route_domain_llm(question_display: str) -> Optional[str]:
    if not _ROUTE_LLM_ENABLE:
        return None
    prompt = (
        "คุณเป็นตัวจัดเส้นทางโดเมนเอกสารให้ระบบ RAG\n"
        "เลือกโดเมนที่เหมาะสมที่สุดสำหรับคำถามนี้ จากรายการ: announcements, regulations, curriculum, auto\n"
        "- announcements: ข่าว/ประกาศ/ปฏิทิน/กำหนดการ\n"
        "- regulations: ระเบียบ/ข้อบังคับ/คำร้อง/วินัย\n"
        "- curriculum: หลักสูตร/รายวิชา/หน่วยกิต/รหัสวิชา\n"
        "- auto: ถ้าไม่แน่ใจหรือข้ามโดเมน\n\n"
        f"คำถาม: {question_display}\n\n"
        "ตอบเป็น JSON เท่านั้น เช่น {\"domain\":\"curriculum\",\"confidence\":0.7}"
    )
    raw = llm_engine.generate(prompt)
    if not raw or raw.strip().startswith('('):
        return None
    obj = _safe_json_obj(raw)
    if not obj:
        return None
    dom = str(obj.get('domain') or '').strip().lower()
    if dom in ('announcements', 'regulations', 'curriculum'):
        return dom
    return None


def _compress_text_extractive(query: str, text: str, max_chars: int) -> str:
    """Cheap, deterministic compression for context packing.

    Goal: keep only likely-relevant lines/sentences to fit token budget.
    """
    q = (query or '').strip()
    t = (text or '').strip()
    if not t:
        return ''
    if not q or max_chars <= 0:
        return t[: max(0, max_chars)]

    # Keywords: keep longer tokens + course codes.
    toks = re.findall(r"[A-Za-z]{2,6}\s*\d{3}|[A-Za-z]{2,6}|[\u0E00-\u0E7F]{2,}", q)
    toks = [x.strip() for x in toks if x and len(x.strip()) >= 2]
    toks = toks[:18]

    lines: List[str] = []
    for ln in t.splitlines():
        s = (ln or '').strip()
        if not s:
            continue
        if any(k in s for k in toks):
            lines.append(s)
        if sum(len(x) for x in lines) >= max_chars:
            break

    if not lines:
        return t[:max_chars]

    out = "\n".join(lines).strip()
    if len(out) > max_chars:
        out = out[:max_chars].rstrip() + ' ...'
    return out


def _rerank_by_embedding(query: str, items: List[Dict], topn: int) -> List[Dict]:
    if not items:
        return []
    n = max(0, min(len(items), int(topn)))
    if n <= 0:
        return items

    head = items[:n]
    tail = items[n:]

    qvec = embed_texts([query], is_query=True)[0]
    texts = [(d.get('text') or '') for d in head]
    dvecs = embed_texts(texts, is_query=False)

    scored: List[Dict] = []
    for d, v in zip(head, dvecs):
        # embed_texts already normalizes; dot product is cosine.
        s = 0.0
        try:
            s = float(sum(float(a) * float(b) for a, b in zip(qvec, v)))
            if math.isnan(s) or math.isinf(s):
                s = 0.0
        except Exception:
            s = 0.0
        scored.append({**d, 'score_rerank': s})

    scored.sort(key=lambda x: (x.get('score_rerank', 0.0), x.get('score_rrf', 0.0)), reverse=True)
    return scored + tail


def _fuse_rrf(lists: List[Tuple[str, List[Dict]]], cap: int) -> List[Dict]:
    """Fuse multiple ranked lists via Reciprocal Rank Fusion."""
    bank: Dict[str, Dict] = {}
    ranks: Dict[str, float] = {}
    for _q, items in lists:
        for r, d in enumerate(items or [], 1):
            dom = (d.get('domain') or '').strip().lower() or 'unknown'
            doc_id = d.get('doc_id') or d.get('source') or f'unk_{r}'
            key = f"{dom}:{doc_id}"
            if key not in bank:
                bank[key] = {**d, 'doc_id': doc_id, 'domain': dom}
            ranks[key] = ranks.get(key, 0.0) + 1.0 / (RRF_K + r)
    merged = [{**bank[k], 'score_rrf': v} for k, v in ranks.items()]
    merged.sort(key=lambda x: x.get('score_rrf', 0.0), reverse=True)
    return merged[:cap]


def _generate_with_engine(prompt: str) -> str:
    user_msg = {'role': 'user', 'content': prompt}
    return llm_engine.generate(prompt, messages=[_SYSTEM_MSG, user_msg])


@lru_cache(maxsize=1)
def _answer_chain():
    return RunnableLambda(_generate_with_engine) | StrOutputParser()


def rag_answer_langchain(question: str, domain: Optional[str] = None) -> Dict[str, Any]:
    """End-to-end RAG using LangChain (LCEL) for orchestration.

    Returns the same shape as the legacy endpoint:
    { question, prompt, answer, contexts, token_est }

    Retrieval intentionally reuses the repo's tuned hybrid logic to keep quality.
    """
    built = _build_rag_prompt_langchain(question=question, domain=domain)
    q_display = built['q_display']
    retrieved = built['retrieved']
    ctx = built['ctx']
    cites = built['cites']
    prompt = built['prompt']

    if _STRUCTURED_ENABLE:
        prompt = (
            f"{prompt}\n\n"
            "ตอบกลับเป็น JSON object เท่านั้น (ห้ามมีข้อความอื่น) โดยมีคีย์:\n"
            "- answer: string (คำตอบเป็น bullet ภาษาไทย)\n"
            "- follow_up_question: string (ถ้าคำถามกำกวมให้ถามกลับ 1 คำถามสั้น ๆ; ถ้าไม่ต้องถามให้เป็น \"\")\n"
            "- citations: array of string (รายการ [source/page] ที่คุณใช้จริงในคำตอบ; ต้องเป็น subset ของรายการที่อนุญาต)\n"
            "ตัวอย่าง: {\"answer\":\"- ... [file/1]\",\"follow_up_question\":\"\",\"citations\":[\"file/1\"]}"
        )

    # If no context, leave answer blank for the caller to apply hard guardrails.
    answer = ''
    structured: Optional[Dict[str, Any]] = None
    follow_up_question = ''
    if retrieved:
        raw = _answer_chain().invoke(prompt)  # type: ignore[no-any-return]
        if _STRUCTURED_ENABLE:
            structured = _safe_json_obj(raw)
            if structured is None:
                # Best-effort retry: some models ignore JSON-only constraints on first attempt.
                retry_prompt = (
                    f"{prompt}\n\n"
                    "คำตอบก่อนหน้าของคุณไม่ใช่ JSON object ที่ถูกต้องตามที่ขอ\n"
                    "กรุณาตอบใหม่อีกครั้ง โดยตอบเป็น JSON object เท่านั้น ห้ามมีข้อความอื่นใดนอกจาก JSON\n"
                    "รูปแบบ: {\"answer\":\"...\",\"follow_up_question\":\"\",\"citations\":[\"source/page\"]}"
                )
                raw2 = _answer_chain().invoke(retry_prompt)  # type: ignore[no-any-return]
                structured = _safe_json_obj(raw2)
                if structured is None:
                    # Fall back to raw (first attempt) if still not structured.
                    structured = None
                else:
                    raw = raw2
            if structured and isinstance(structured.get('answer'), str):
                answer = (structured.get('answer') or '').strip()
                fu = structured.get('follow_up_question')
                if isinstance(fu, str):
                    follow_up_question = fu.strip()
            else:
                answer = (raw or '').strip()
        else:
            answer = (raw or '').strip()

    # Optional: enforce at least one citation per bullet line using allowed cites.
    # This never invents new citations; it only uses the ones we already allowed.
    if _ENFORCE_CITATIONS and answer:
        try:
            allowed = [str(x) for x in (cites or {}).values() if (x or '').strip()]
            answer = _enforce_citations(answer, allowed)
        except Exception:
            pass

    out: Dict[str, Any] = {
        'question': question,
        'prompt': prompt,
        'answer': answer,
        'contexts': [
            {
                'doc_id': r.get('doc_id'),
                'domain': r.get('domain'),
                'source': r.get('source'),
                'path': r.get('path'),
                'page_start': r.get('page_start'),
                'page_end': r.get('page_end'),
                'score_rrf': r.get('score_rrf'),
            }
            for r in retrieved
        ],
        'token_est': est_tokens(ctx),
    }

    if _STRUCTURED_ENABLE:
        # Keep structured.citations aligned with the final answer when possible.
        if isinstance(structured, dict):
            used = _extract_citations_from_text(answer)
            allowed_set = {str(x) for x in (cites or {}).values() if (x or '').strip()}
            used = [c for c in used if c in allowed_set]
            structured = {**structured}
            structured.setdefault('citations', used)
            # If enforcement appended a fallback cite, ensure it's reflected.
            if used:
                structured['citations'] = _dedupe_keep_order([str(x) for x in used], cap=24)
        out['structured'] = structured
        out['follow_up_question'] = follow_up_question

    return out


def _build_rag_prompt_langchain(question: str, domain: Optional[str] = None) -> Dict[str, Any]:
    """Shared retrieval+prompt builder used by both query and answer endpoints."""
    q_display = normalize_question(question)
    q_search = search_query_from_question(question)

    dom = (domain or '').strip().lower()
    if not dom:
        # Prefer deterministic heuristic routing first (stable + fast).
        dom = infer_domain(q_display) or ''
        # Use LLM router only when heuristic is unclear.
        if not dom:
            dom = _route_domain_llm(q_display) or ''
    dom = dom or None

    # Multi-query retrieval (best-effort): use LLM to generate query variants,
    # retrieve for each query, then fuse with RRF.
    variants: List[str] = []
    if _MULTIQUERY_ENABLE and (_MULTIQUERY_ALL or (dom == 'curriculum') or (dom is None)):
        variants = _multiquery_variants(q_display, q_search, dom)
    queries = _dedupe_keep_order([q_search, *variants], cap=1 + len(variants))

    wants_listy = (
        'LNG' in q_display.upper()
        and any(t in q_display for t in ('เลือกเรียน', 'มีวิชา', 'วิชาอะไร', 'เลือกได้', 'ตัวเลือก'))
    )
    cap = max(MAX_CONTEXTS, 20) if wants_listy else MAX_CONTEXTS

    retrieved_lists: List[Tuple[str, List[Dict]]] = []

    def _retrieve_one(q: str) -> Tuple[str, List[Dict]]:
        def _fallback_domains(primary: str) -> List[str] | None:
            p = (primary or '').strip().lower()
            if p == 'announcements':
                return ['announcements', 'regulations']
            if p == 'regulations':
                return ['regulations', 'announcements']
            if p == 'curriculum':
                # Curriculum questions sometimes need registrar schedules.
                return ['curriculum', 'announcements', 'regulations']
            return None

        if dom:
            items = retrieve_by_domain(q, domain=dom)
            if len(items) < 4:
                doms = _fallback_domains(dom)
                items = retrieve_all_domains(q, domains=doms)
        else:
            items = retrieve_all_domains(q)
        return q, items

    if _PARALLEL_ENABLE and len(queries) > 1:
        workers = max(1, min(12, int(_PARALLEL_WORKERS)))
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = [ex.submit(_retrieve_one, q) for q in queries]
            for fut in as_completed(futs):
                try:
                    retrieved_lists.append(fut.result())
                except Exception:
                    continue
        order = {q: i for i, q in enumerate(queries)}
        retrieved_lists.sort(key=lambda x: order.get(x[0], 10**9))
    else:
        for q in queries:
            retrieved_lists.append(_retrieve_one(q))

    retrieved = _fuse_rrf(retrieved_lists, cap=cap)

    # Optional rerank (embedding-based) to reduce noise.
    if _RERANK_ENABLE and retrieved and (_RERANK_ALL or (dom == 'curriculum')):
        try:
            retrieved = _rerank_by_embedding(q_search, retrieved, topn=_RERANK_TOPN)
            retrieved = retrieved[:cap]
        except Exception:
            pass

    # Optional extractive compression to pack more relevant context.
    if _COMPRESS_ENABLE and retrieved and (_COMPRESS_ALL or (dom == 'curriculum')):
        try:
            max_chars = max(200, int(_COMPRESS_MAX_CHARS))
            compressed: List[Dict] = []
            for d in retrieved:
                txt = (d.get('text') or '')
                ctxt = _compress_text_extractive(q_display, txt, max_chars=max_chars)
                compressed.append({**d, 'text': ctxt or txt})
            retrieved = compressed
        except Exception:
            pass

    ctx, cites = pack_context(retrieved)
    prompt = build_prompt(q_display, ctx, cites)

    return {
        'q_display': q_display,
        'q_search': q_search,
        'domain': dom,
        'retrieved': retrieved,
        'ctx': ctx,
        'cites': cites,
        'prompt': prompt,
    }


def rag_query_langchain(question: str, domain: Optional[str] = None) -> Dict[str, Any]:
    """Query-only RAG using the LangChain orchestration retrieval path.

    Shape matches legacy rag_query/rag_query_domain outputs:
    { prompt, contexts, token_est }
    """
    built = _build_rag_prompt_langchain(question=question, domain=domain)
    retrieved = built['retrieved']
    prompt = built['prompt']
    ctx = built['ctx']

    return {
        'prompt': prompt,
        'contexts': [
            {
                'doc_id': r.get('doc_id'),
                'domain': r.get('domain'),
                'source': r.get('source'),
                'path': r.get('path'),
                'page_start': r.get('page_start'),
                'page_end': r.get('page_end'),
                'score_rrf': r.get('score_rrf'),
            }
            for r in (retrieved or [])
        ],
        'token_est': est_tokens(ctx),
    }
