#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import mlflow_utils as mlf


DEFAULT_ABSTAIN_TERMS = [
    'ไม่พบข้อความยืนยัน',
    'ไม่ได้กล่าวตรง',
    'ไม่สามารถระบุวันที่ชัดเจน',
    'ไม่มีข้อมูลระบุวันที่แน่นอน',
    'ไม่พบข้อความยืนยันวันหรือวันที่',
]


@dataclass
class Case:
    case_id: str
    domain: str
    question: str
    must_contain: List[str] = field(default_factory=list)
    must_contain_any: List[List[str]] = field(default_factory=list)
    must_contain_numbers: List[str] = field(default_factory=list)
    expect_abstain: bool = False
    expected_sources: List[str] = field(default_factory=list)


@dataclass
class CaseResult:
    case_id: str
    domain: str
    question: str
    answer: str
    latency_ms: float
    contexts_count: int
    token_est: int
    sources: List[str]
    answer_sources: List[str]
    passed: bool
    abstain_hit: bool
    source_hit: bool
    error: Optional[str] = None


SMOKE_CASES: List[Case] = [
    Case(
        case_id='ann_exact_date_guardrail',
        domain='announcements',
        question='ประกาศค่าประกันภัยมีผลบังคับตั้งแต่วันที่เท่าไร',
        expect_abstain=True,
        expected_sources=['insurance'],
    ),
    Case(
        case_id='ann_accident_insurance_fee',
        domain='announcements',
        question='มหาวิทยาลัยเก็บค่าประกันภัยอุบัติเหตุคืออะไร?',
        must_contain=['500 บาท'],
        must_contain_numbers=['500'],
        expected_sources=['insurance'],
    ),
    Case(
        case_id='ann_insurance_fee_per_year',
        domain='announcements',
        question='นักศึกษาต้องจ่ายค่าประกันภัยเท่าไรต่อปี?',
        must_contain=['500 บาท'],
        must_contain_numbers=['500'],
        expected_sources=['insurance'],
    ),
    Case(
        case_id='reg_conflict_priority',
        domain='regulations',
        question='ถ้าข้อความในระเบียบอื่นขัดกับระเบียบการสอบจะให้ใช้เอกสารไหน?',
        must_contain_any=[['ระเบียบนี้แทน', 'ให้ใช้ระเบียบนี้แทน'], ['การสอบ']],
        expected_sources=['rule_exam2560'],
    ),
    Case(
        case_id='reg_repeal_old_rule',
        domain='regulations',
        question='ระเบียบการสอบใหม่ยกเลิกระเบียบเก่าอะไร?',
        must_contain_any=[['ข้อ 26'], ['2557', 'พ.ศ. 2557']],
        expected_sources=['rule57_2', '129'],
    ),
    Case(
        case_id='cur_total_credits',
        domain='curriculum',
        question='หลักสูตรวิศวกรรมคอมพิวเตอร์ต้องศึกษารวมกี่หน่วยกิต?',
        must_contain=['130 หน่วยกิต'],
        must_contain_numbers=['130'],
        expected_sources=['foe10_', 'วศ.บ.วิศวกรรมคอมพิวเตอร์_2564'],
    ),
    Case(
        case_id='cur_cpe100_lookup',
        domain='curriculum',
        question='วิชา CPE 100 คืออะไร และมีกี่หน่วยกิต?',
        must_contain=['การเขียนโปรแกรมคอมพิวเตอร์สำหรับวิศวกร'],
        must_contain_numbers=['3'],
        expected_sources=['วศ_บ_', 'foe10_', 'foe10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564'],
    ),
    Case(
        case_id='cur_cpe101_lookup',
        domain='curriculum',
        question='วิชา CPE 101 คืออะไร และมีกี่หน่วยกิต?',
        must_contain=['เปิดโลกวิศวกรรมศาสตร์'],
        must_contain_numbers=['3'],
        expected_sources=['foe10_', 'วศ.บ.วิศวกรรมคอมพิวเตอร์_2564'],
    ),
    Case(
        case_id='cur_cpe111_lookup',
        domain='curriculum',
        question='วิชา CPE 111 คืออะไร และมีกี่หน่วยกิต?',
        must_contain=['คณิตศาสตร์ดิสครีตสำหรับวิศวกรคอมพิวเตอร์'],
        must_contain_numbers=['3'],
        expected_sources=['foe10_', 'วศ.บ.วิศวกรรมคอมพิวเตอร์_2564'],
    ),
    Case(
        case_id='cur_cpe112_lookup',
        domain='curriculum',
        question='วิชา CPE 112 คืออะไร และมีกี่หน่วยกิต?',
        must_contain=['การเขียนโปรแกรมด้วยโครงสร้างข้อมูล'],
        must_contain_numbers=['3'],
        expected_sources=['foe10_', 'วศ.บ.วิศวกรรมคอมพิวเตอร์_2564'],
    ),
    Case(
        case_id='cur_cpe121_lookup',
        domain='curriculum',
        question='วิชา CPE 121 คืออะไร และมีกี่หน่วยกิต?',
        must_contain=['พื้นฐานวงจรไฟฟ้าและอิเล็กทรอนิกส์'],
        must_contain_numbers=['3'],
        expected_sources=['foe10_', 'วศ.บ.วิศวกรรมคอมพิวเตอร์_2564'],
    ),
    Case(
        case_id='cur_mth101_lookup',
        domain='curriculum',
        question='วิชา MTH 101 คืออะไร และมีกี่หน่วยกิต?',
        must_contain=['คณิตศาสตร์ 1'],
        must_contain_numbers=['3'],
        expected_sources=['foe10_', 'วศ.บ.วิศวกรรมคอมพิวเตอร์_2564'],
    ),
    Case(
        case_id='cur_phy103_lookup',
        domain='curriculum',
        question='วิชา PHY 103 คืออะไร และมีกี่หน่วยกิต?',
        must_contain=['ฟิสิกส์ทั่วไปสำหรับนักศึกษาวิศวกรรมศาสตร์ 1'],
        must_contain_numbers=['3'],
        expected_sources=['foe10_', 'วศ.บ.วิศวกรรมคอมพิวเตอร์_2564'],
    ),
]


MEDIUM_EXTRA_CASES: List[Case] = [
    Case(
        case_id='ann_insurance_decider',
        domain='announcements',
        question='ใครมีอำนาจวินิจฉัยเมื่อเกิดปัญหากับประกาศนี้?',
        must_contain=['อธิการบดี'],
        expected_sources=['fee2567update', 'eng2561', '137'],
    ),
    Case(
        case_id='ann_postal_title',
        domain='announcements',
        question='ประกาศค่าธรรมเนียมการจัดส่งเอกสารมีชื่ออะไร?',
        must_contain=['อัตราค่าธรรมเนียมการบริการจัดส่งเอกสารสำคัญทางการศึกษาทางไปรษณีย์'],
        must_contain_numbers=['2562'],
        expected_sources=['t_fee'],
    ),
    Case(
        case_id='ann_postal_collector',
        domain='announcements',
        question='ใครเป็นผู้เรียกเก็บค่าธรรมเนียมการจัดส่งเอกสาร?',
        must_contain=['สำนักงานทะเบียนนักศึกษา'],
        expected_sources=['t_fee'],
    ),
    Case(
        case_id='reg_exam_dress',
        domain='regulations',
        question='นักศึกษาต้องแต่งตัวแบบไหนเมื่อเข้าห้องสอบ?',
        must_contain=['ชุดนักศึกษา'],
        expected_sources=['rule_exam2560'],
    ),
    Case(
        case_id='reg_exam_bring_id',
        domain='regulations',
        question='นักศึกษาต้องนำสิ่งของอะไรเข้าห้องสอบ?',
        must_contain_any=[['บัตรนักศึกษา', 'ใบแทนบัตรประจำตัวนักศึกษา']],
        expected_sources=['rule_exam2560'],
    ),
    Case(
        case_id='reg_exam_calculator',
        domain='regulations',
        question='นักศึกษาเอาเครื่องคิดเลขเข้าห้องสอบได้หรือไม่?',
        must_contain_any=[['อาจารย์ประจำวิชาได้อนุญาต', 'ได้รับอนุญาตจากอาจารย์'], ['1 เครื่อง', 'คนละ 1 เครื่อง']],
        expected_sources=['rule_exam2560', 'calculator2023'],
    ),
    Case(
        case_id='cur_cpe222_lookup',
        domain='curriculum',
        question='วิชา CPE 222 คืออะไร และมีกี่หน่วยกิต?',
        must_contain=['อิเล็กทรอนิกส์ดิจิทัลและการออกแบบวงจรเชิงตรรกะ'],
        must_contain_numbers=['3'],
        expected_sources=['foe10_', 'วศ.บ.วิศวกรรมคอมพิวเตอร์_2564'],
    ),
    Case(
        case_id='cur_cpe231_lookup',
        domain='curriculum',
        question='วิชา CPE 231 คืออะไร และมีกี่หน่วยกิต?',
        must_contain=['ขั้นตอนวิธี'],
        must_contain_numbers=['3'],
        expected_sources=['foe10_', 'วศ.บ.วิศวกรรมคอมพิวเตอร์_2564'],
    ),
    Case(
        case_id='cur_cpe232_lookup',
        domain='curriculum',
        question='วิชา CPE 232 คืออะไร และมีกี่หน่วยกิต?',
        must_contain=['แบบจำลองข้อมูล'],
        must_contain_numbers=['3'],
        expected_sources=['foe10_', 'วศ.บ.วิศวกรรมคอมพิวเตอร์_2564'],
    ),
    Case(
        case_id='cur_cpe241_lookup',
        domain='curriculum',
        question='วิชา CPE 241 คืออะไร และมีกี่หน่วยกิต?',
        must_contain=['ระบบฐานข้อมูล'],
        must_contain_numbers=['3'],
        expected_sources=['foe10_', 'วศ.บ.วิศวกรรมคอมพิวเตอร์_2564'],
    ),
    Case(
        case_id='cur_cpe333_lookup',
        domain='curriculum',
        question='วิชา CPE 333 คืออะไร และมีกี่หน่วยกิต?',
        must_contain=['ระบบปฏิบัติการ'],
        must_contain_numbers=['3'],
        expected_sources=['foe10_', 'วศ.บ.วิศวกรรมคอมพิวเตอร์_2564'],
    ),
    Case(
        case_id='cur_cpe334_lookup',
        domain='curriculum',
        question='วิชา CPE 334 คืออะไร และมีกี่หน่วยกิต?',
        must_contain=['วิศวกรรมซอฟต์แวร์'],
        must_contain_numbers=['3'],
        expected_sources=['foe10_', 'วศ.บ.วิศวกรรมคอมพิวเตอร์_2564'],
    ),
    Case(
        case_id='cur_gen101_lookup',
        domain='curriculum',
        question='วิชา GEN 101 คืออะไร และมีกี่หน่วยกิต?',
        must_contain=['พลศึกษา'],
        must_contain_numbers=['1'],
        expected_sources=['foe10_', 'วศ.บ.วิศวกรรมคอมพิวเตอร์_2564'],
    ),
    Case(
        case_id='cur_gen111_lookup',
        domain='curriculum',
        question='วิชา GEN 111 คืออะไร และมีกี่หน่วยกิต?',
        must_contain=['มนุษย์กับหลักจริยศาสตร์เพื่อการดำเนินชีวิต'],
        must_contain_numbers=['3'],
        expected_sources=['foe10_', 'วศ.บ.วิศวกรรมคอมพิวเตอร์_2564'],
    ),
    Case(
        case_id='cur_gen231_lookup',
        domain='curriculum',
        question='วิชา GEN 231 คืออะไร และมีกี่หน่วยกิต?',
        must_contain=['มหัศจรรย์แห่งความคิด'],
        must_contain_numbers=['3'],
        expected_sources=['foe10_', 'วศ.บ.วิศวกรรมคอมพิวเตอร์_2564'],
    ),
    Case(
        case_id='cur_lng223_lookup',
        domain='curriculum',
        question='วิชา LNG 223 คืออะไร และมีกี่หน่วยกิต?',
        must_contain=['ภาษาอังกฤษเพื่อการสื่อสารในที่ทำงาน'],
        must_contain_numbers=['3'],
        expected_sources=['foe10_', 'วศ.บ.วิศวกรรมคอมพิวเตอร์_2564'],
    ),
    Case(
        case_id='cur_mth234_lookup',
        domain='curriculum',
        question='วิชา MTH 234 คืออะไร และมีกี่หน่วยกิต?',
        must_contain=['พีชคณิตเชิงเส้น'],
        must_contain_numbers=['3'],
        expected_sources=['foe10_', 'วศ.บ.วิศวกรรมคอมพิวเตอร์_2564'],
    ),
    Case(
        case_id='cur_chm103_lookup',
        domain='curriculum',
        question='วิชา CHM 103 คืออะไร และมีกี่หน่วยกิต?',
        must_contain=['เคมีพื้นฐาน'],
        must_contain_numbers=['3'],
        expected_sources=['foe10_', 'วศ.บ.วิศวกรรมคอมพิวเตอร์_2564'],
    ),
    Case(
        case_id='cur_sta302_lookup',
        domain='curriculum',
        question='วิชา STA 302 คืออะไร และมีกี่หน่วยกิต?',
        must_contain=['สถิติสำหรับวิศวกร'],
        must_contain_numbers=['3'],
        expected_sources=['foe10_', 'วศ.บ.วิศวกรรมคอมพิวเตอร์_2564'],
    ),
]


CASE_SUITES = {
    'smoke': SMOKE_CASES,
    'medium': [*SMOKE_CASES, *MEDIUM_EXTRA_CASES],
}


def _normalize(text: str) -> str:
    return ' '.join((text or '').strip().lower().split())


def _contains_all(answer: str, parts: List[str]) -> bool:
    text = _normalize(answer)
    return all(_normalize(part) in text for part in parts)


def _contains_any_groups(answer: str, groups: List[List[str]]) -> bool:
    text = _normalize(answer)
    for group in groups:
        if not any(_normalize(part) in text for part in group):
            return False
    return True


def _contains_all_numbers(answer: str, numbers: List[str]) -> bool:
    text = _normalize(answer)
    return all(str(number) in text for number in numbers)


def _extract_sources(contexts: List[Dict[str, Any]]) -> List[str]:
    out: List[str] = []
    seen = set()
    for ctx in contexts or []:
        src = str(ctx.get('source') or ctx.get('path') or '').strip()
        if not src:
            continue
        name = src.replace('\\', '/').split('/')[-1]
        if name in seen:
            continue
        seen.add(name)
        out.append(name)
    return out


def _extract_answer_sources(answer: str) -> List[str]:
    out: List[str] = []
    seen = set()
    for raw in re.findall(r'\[([^\[\]]+?)/(?:\d+)\]', answer or ''):
        name = str(raw).strip().replace('\\', '/').split('/')[-1]
        if not name or name in seen:
            continue
        seen.add(name)
        out.append(name)
    return out


def _source_hit(context_sources: List[str], answer_sources: List[str], expected_sources: List[str]) -> bool:
    if not expected_sources:
        return True
    joined = ' '.join(context_sources + answer_sources).lower()
    return any(expect.lower() in joined for expect in expected_sources)


def _get_cases(suite: str) -> List[Case]:
    try:
        return CASE_SUITES[suite]
    except KeyError as exc:
        raise ValueError(f'Unknown suite: {suite}') from exc


def _abstain_hit(answer: str) -> bool:
    text = _normalize(answer)
    return any(_normalize(term) in text for term in DEFAULT_ABSTAIN_TERMS)


def evaluate_case(base_url: str, case: Case, timeout_s: float) -> CaseResult:
    start = time.perf_counter()
    try:
        resp = requests.post(
            base_url.rstrip('/') + '/rag/answer',
            json={'domain': case.domain, 'question': case.question},
            timeout=timeout_s,
        )
        resp.raise_for_status()
        payload = resp.json()
    except Exception as exc:
        latency_ms = (time.perf_counter() - start) * 1000.0
        return CaseResult(
            case_id=case.case_id,
            domain=case.domain,
            question=case.question,
            answer='',
            latency_ms=latency_ms,
            contexts_count=0,
            token_est=0,
            sources=[],
            answer_sources=[],
            passed=False,
            abstain_hit=False,
            source_hit=False,
            error=f'{type(exc).__name__}: {exc}',
        )

    latency_ms = (time.perf_counter() - start) * 1000.0
    answer = str(payload.get('answer') or '').strip()
    contexts = list(payload.get('contexts') or [])
    sources = _extract_sources(contexts)
    answer_sources = _extract_answer_sources(answer)
    abstain_hit = _abstain_hit(answer)
    source_hit = _source_hit(sources, answer_sources, case.expected_sources)

    passed = source_hit
    if case.expect_abstain:
        passed = passed and abstain_hit
    else:
        passed = (
            passed
            and _contains_all(answer, case.must_contain)
            and _contains_any_groups(answer, case.must_contain_any)
            and _contains_all_numbers(answer, case.must_contain_numbers)
        )

    return CaseResult(
        case_id=case.case_id,
        domain=case.domain,
        question=case.question,
        answer=answer,
        latency_ms=latency_ms,
        contexts_count=len(contexts),
        token_est=int(payload.get('token_est') or 0),
        sources=sources,
        answer_sources=answer_sources,
        passed=passed,
        abstain_hit=abstain_hit,
        source_hit=source_hit,
        error=None,
    )


def _safe_get_json(url: str, timeout_s: float) -> Dict[str, Any]:
    try:
        resp = requests.get(url, timeout=timeout_s)
        resp.raise_for_status()
        return dict(resp.json() or {})
    except Exception as exc:
        return {'error': f'{type(exc).__name__}: {exc}'}


def _write_reports(results: List[CaseResult], report_stem: str) -> List[str]:
    reports_dir = Path('reports')
    reports_dir.mkdir(parents=True, exist_ok=True)
    json_path = reports_dir / f'{report_stem}.json'
    md_path = reports_dir / f'{report_stem}.md'

    payload = {
        'generated_at': datetime.now().isoformat(),
        'results': [asdict(r) for r in results],
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')

    lines = [f'# Targeted Eval {report_stem}', '']
    for result in results:
        status = 'PASS' if result.passed else 'FAIL'
        lines.append(f'## {result.case_id} [{status}]')
        lines.append(f'- domain: {result.domain}')
        lines.append(f'- latency_ms: {result.latency_ms:.1f}')
        lines.append(f'- contexts: {result.contexts_count}')
        lines.append(f'- source_hit: {result.source_hit}')
        lines.append(f'- abstain_hit: {result.abstain_hit}')
        if result.sources:
            lines.append(f'- sources: {", ".join(result.sources[:6])}')
        if result.answer_sources:
            lines.append(f'- answer_sources: {", ".join(result.answer_sources[:6])}')
        if result.error:
            lines.append(f'- error: {result.error}')
        lines.append(f'- question: {result.question}')
        lines.append(f'- answer: {result.answer[:600]}')
        lines.append('')

    md_path.write_text('\n'.join(lines).strip() + '\n', encoding='utf-8')
    return [str(json_path), str(md_path)]


def main() -> int:
    ap = argparse.ArgumentParser(description='Run targeted RAG evaluation and log to MLflow.')
    ap.add_argument('--base-url', default='http://127.0.0.1:8001')
    ap.add_argument('--timeout', type=float, default=90.0)
    ap.add_argument('--tracking-uri', default='http://127.0.0.1:5000')
    ap.add_argument('--experiment', default=os.getenv('MLFLOW_EVAL_EXPERIMENT', 'cpe-chat-eval'))
    ap.add_argument('--run-name', default='targeted_eval_guardrails')
    ap.add_argument('--suite', choices=sorted(CASE_SUITES), default='smoke')
    args = ap.parse_args()

    os_environ = {
        'MLFLOW_ENABLE': '1',
        'MLFLOW_TRACKING_URI': args.tracking_uri,
        'MLFLOW_EXPERIMENT': args.experiment,
    }
    for key, value in os_environ.items():
        import os
        os.environ[key] = value

    health = _safe_get_json(args.base_url.rstrip('/') + '/health', timeout_s=5.0)
    config = _safe_get_json(args.base_url.rstrip('/') + '/debug/config', timeout_s=5.0)

    cases = _get_cases(args.suite)
    results = [evaluate_case(args.base_url, case, timeout_s=args.timeout) for case in cases]
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    abstain_cases = sum(1 for case in cases if case.expect_abstain)
    abstain_hits = sum(1 for r, case in zip(results, cases) if case.expect_abstain and r.abstain_hit)
    avg_latency_ms = sum(r.latency_ms for r in results) / max(1, total)
    avg_contexts = sum(r.contexts_count for r in results) / max(1, total)
    source_hit_rate = sum(1 for r in results if r.source_hit) / max(1, total)
    error_count = sum(1 for r in results if r.error)

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_stem = f'targeted_eval_guardrails_{args.suite}_{ts}'
    artifact_paths = _write_reports(results, report_stem)

    context_payload = {
        'health': health,
        'debug_config': config,
        'results': [asdict(r) for r in results],
        'env': mlf.env_snapshot(),
    }

    with mlf.start_run(run_name=args.run_name, tags={'script': 'scripts/eval_targeted_mlflow.py'}):
        mlf.log_params(
            {
                'base_url': args.base_url,
                'suite': args.suite,
                'cases': total,
                'tracking_uri': args.tracking_uri,
                'experiment': args.experiment,
            }
        )
        mlf.log_metrics(
            {
                'pass_count': passed,
                'pass_rate': passed / max(1, total),
                'avg_latency_ms': avg_latency_ms,
                'avg_contexts': avg_contexts,
                'source_hit_rate': source_hit_rate,
                'error_count': error_count,
                'abstain_case_count': abstain_cases,
                'abstain_hit_rate': abstain_hits / max(1, abstain_cases),
            }
        )
        mlf.log_artifacts(artifact_paths)
        mlf.log_dict_artifact(context_payload, artifact_file=f'{report_stem}_context.json')

    print(json.dumps(
        {
            'report_stem': report_stem,
            'pass_count': passed,
            'total': total,
            'pass_rate': round(passed / max(1, total), 4),
            'avg_latency_ms': round(avg_latency_ms, 2),
            'abstain_hit_rate': round(abstain_hits / max(1, abstain_cases), 4),
            'source_hit_rate': round(source_hit_rate, 4),
            'artifacts': artifact_paths,
        },
        ensure_ascii=False,
        indent=2,
    ))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())