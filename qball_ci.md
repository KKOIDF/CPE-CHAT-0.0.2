# Regression Eval Summary

Generated: 2026-04-16T22:01:28.397898
Input: data/question_bank_250_general_th.json
Base URL: http://127.0.0.1:8001

## Headline

- total cases: 342
- overall pass rate: 0.2953

### Retrieval Metrics
- top-1 hit rate: 0.8041
- top-3 hit rate: 0.9474
- top-5 hit rate: 0.9474
- top-K hit rate: 0.8947
- mean reciprocal rank (mrr): 0.8582

### Answer Quality Metrics
- answer keyword hit rate: 0.2982
- average quality score (1-5): 0.0000
- % correct answers: 0.2982
- % hallucination: 0.0000
- % answerable handled correctly: 0.3450
- citation validity (groundedness): 0.9386
- citation precision: 0.9143
- citation recall: 0.9265
- citation micro precision: 0.9049
- citation micro recall: 0.2739
- must-not contain pass rate: 1.0000
- runtime error rate: 0.0000
- runtime error count: 0

### Latency Metrics
- avg total latency ms: 3660.95
- median total latency ms: 1166.82
- p95 total latency ms: 15148.52
- avg retrieval latency ms: 1023.54
- median retrieval latency ms: 1038.62
- p95 retrieval latency ms: 2055.31
- avg generation latency ms: 5274.83
- median generation latency ms: 5239.01
- p95 generation latency ms: 15762.16

## Coverage

- total questions: 342
- questions by domain: announcements=135, curriculum=99, general=29, regulations=79
- questions by difficulty: easy=74, hard=75, medium=193
- questions by question type: ambiguous=6, factual=102, multi-hop=57, multi_turn_dependency=6, noisy=6, policy_conflict=6, procedural=85, unanswerable=20, verification=54

## Retrieval By Domain

- announcements: total=135, top1=0.7704, top3=0.8889, top5=0.8889, mrr=0.8148
- curriculum: total=99, top1=0.8990, top3=0.9899, top5=0.9899, mrr=0.9444
- general: total=29, top1=1.0000, top3=1.0000, top5=1.0000, mrr=1.0000
- regulations: total=79, top1=0.6709, top3=0.9747, top5=0.9747, mrr=0.7722

## Domain Monitor

- announcements: total=135, overall=0.0222, answer=0.0296, retrieval=0.8889, citation=1.0000, avg_latency_ms=1396.54, p95_latency_ms=1962.59
- curriculum: total=99, overall=0.6061, answer=0.6061, retrieval=0.9899, citation=0.9899, avg_latency_ms=6091.87, p95_latency_ms=17371.49
- general: total=29, overall=0.0000, answer=0.0000, retrieval=0.3793, citation=0.3793, avg_latency_ms=6178.20, p95_latency_ms=12105.89
- regulations: total=79, overall=0.4810, answer=0.4810, retrieval=0.9747, citation=0.9747, avg_latency_ms=3560.13, p95_latency_ms=12909.79

## By Category

- uncategorized: total=342, overall=0.2953, answer=0.2982, retrieval=0.8947, top1=0.8041, top3=0.9474, top5=0.9474, citation=0.9386

## Error Tag Counts

- retrieve_found_but_answer_incomplete: 205
- pass_or_unclassified: 101
- context_conflict: 21
- retrieve_not_found: 18
- answer_out_of_domain: 3

## Adaptive Metrics

- retrieval_adaptive_retry_triggered: 0.3596
- retrieval_adaptive_retry_succeeded: 0.3099
- retrieval_fallback_all_domains_triggered: 0.0000
- retrieval_fallback_all_domains_succeeded: 0.0000
- structured_rescue_triggered: 0.1228
- structured_rescue_succeeded: 0.1228
- curriculum_bypass_vector_triggered: 0.2222
- low_confidence_detected: 0.3830
- initial_retrieval_doc_count: 3.1696
- retry_retrieval_doc_count: 1.5088
- initial_top_score: 0.2049
- retry_top_score: 0.1120

## Answer Schema Metrics By Task

- announcement_procedure: cases=1, attempted=1, success=1, attempt_rate=1.0000, success_rate_of_attempts=1.0000, avg_missing_before=2.0000, avg_missing_after=0.0000
- announcement_temporal: cases=154, attempted=0, success=0, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000
- course_factual: cases=31, attempted=10, success=3, attempt_rate=0.3226, success_rate_of_attempts=0.3000, avg_missing_before=0.4194, avg_missing_after=0.3226
- none: cases=139, attempted=0, success=0, attempt_rate=0.0000, success_rate_of_attempts=0.0000, avg_missing_before=0.0000, avg_missing_after=0.0000
- prerequisite: cases=2, attempted=2, success=2, attempt_rate=1.0000, success_rate_of_attempts=1.0000, avg_missing_before=1.0000, avg_missing_after=0.0000
- regulation_procedure: cases=15, attempted=5, success=5, attempt_rate=0.3333, success_rate_of_attempts=1.0000, avg_missing_before=1.4667, avg_missing_after=0.8000

## Failed Cases Top 20

- qb_179 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=285.0, tags=retrieve_found_but_answer_incomplete, error=none
- qb_177 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=290.8, tags=retrieve_found_but_answer_incomplete, error=none
- qb_184 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=323.0, tags=retrieve_found_but_answer_incomplete, error=none
- qb_167 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=324.6, tags=retrieve_found_but_answer_incomplete, error=none
- qb_236 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=366.0, tags=retrieve_found_but_answer_incomplete, error=none
- qb_099 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=378.8, tags=retrieve_found_but_answer_incomplete, error=none
- qb_303 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=758.7, tags=retrieve_found_but_answer_incomplete, error=none
- qb_306 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=787.9, tags=retrieve_found_but_answer_incomplete, error=none
- qb_203 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=802.7, tags=retrieve_found_but_answer_incomplete, error=none
- qb_201 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=839.2, tags=retrieve_not_found, error=none
- qb_243 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=840.7, tags=retrieve_found_but_answer_incomplete, error=none
- qb_098 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=842.8, tags=retrieve_found_but_answer_incomplete, error=none
- qb_055 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=869.0, tags=retrieve_found_but_answer_incomplete, error=none
- qb_342 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=870.6, tags=retrieve_found_but_answer_incomplete, error=none
- qb_143 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=887.0, tags=retrieve_found_but_answer_incomplete, error=none
- qb_084 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=900.3, tags=retrieve_not_found, error=none
- qb_253 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=904.5, tags=retrieve_found_but_answer_incomplete, error=none
- qb_217 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=912.2, tags=retrieve_found_but_answer_incomplete, error=none
- qb_257 (uncategorized): coverage=0.00, retrieval=True, citation=True, must_not=True, latency_ms=926.4, tags=retrieve_found_but_answer_incomplete, error=none
- qb_002 (uncategorized): coverage=0.00, retrieval=False, citation=True, must_not=True, latency_ms=933.9, tags=retrieve_not_found, error=none

## Executive Reframe (342-case)

- ชุด 40 เคสที่ผ่าน 100% ยังไม่ generalize ไปยังชุด 342 เคส
- bottleneck หลักย้ายจาก retrieval ไปที่ answering policy orchestration
- หลักฐานสำคัญ: answer_hit_rate=0.2982 เทียบ retrieval_hit_rate=0.8947
- failure mode หลัก: retrieve_found_but_answer_incomplete=205 สูงกว่า retrieve_not_found=18 มาก

## Root Cause Matrix

| Workstream | Symptom (หลักฐาน) | Root Cause ที่เป็นไปได้ | ขอบเขตผลกระทบ | Priority |
|---|---|---|---|---|
| Announcements intent routing | domain pass 2.2% แต่ retrieval hit 88.9%, citation validity 1.0 | intent collapse ไป answer แบบ temporal/date lookup แม้คำถามเป็น verification/procedure/after-deadline/follow-up channel | สูงมาก (135 เคส, โดยเฉพาะ procedural + verification) | P0 |
| Curriculum exact-match guard | บางเคสตอบรหัสใกล้เคียง (nearest-code) แทนการปฏิเสธอย่างมีเหตุผล | ขาด hard guard ว่า course code ต้อง exact match ก่อน commit คำตอบเชิง factual | กลาง-สูง (course factual trust) | P0 |
| Regulations procedural schema | retrieval ถูกแต่โดน incomplete ในโจทย์ verification/procedural | answer schema ยังไม่บังคับ slot ขั้นตอน/เงื่อนไข/ข้อจำกัด/ช่องทางติดต่อครบ | สูง (79 เคส โดยเฉพาะ procedural) | P1 |
| General unanswerable template | domain general ผ่าน 0%; มี context_conflict/missing citations ในเคสที่ควร abstain | refusal template และ citation policy สำหรับ no-evidence ยังไม่สอดคล้อง evaluator | กลาง (29 เคส แต่กระทบ reliability) | P1 |

## Fix Plan (Production-Oriented)

### Workstream A: Announcements Router v2 (P0)

- เป้าหมาย: แยก intent เป็น 5 คลาสก่อนเข้าตัวสร้างคำตอบ
	- `date_lookup`
	- `verification_update_exists`
	- `what_should_i_do`
	- `after_deadline_remedy`
	- `where_to_follow_updates`
- กติกา policy:
	- ห้ามตอบเป็นแค่วันที่ หาก intent ไม่ใช่ `date_lookup`
	- บังคับ output frame ตาม intent (เช่น verification ต้องมีสถานะ + หลักฐาน + next step)
- Acceptance gates:
	- announcements overall pass >= 0.45
	- ลด `retrieve_found_but_answer_incomplete` ใน announcements ลงอย่างน้อย 50%

### Workstream B: Curriculum Exact-Code + Abstention Guard (P0)

- เป้าหมาย: ปิด nearest-code hallucination
- กติกา policy:
	- ตรวจจับ course code จากคำถามและหลักฐาน
	- หากไม่มี exact match ให้ตอบแบบยืนยันไม่ได้ (ไม่เดารหัสใกล้เคียง)
	- หากข้อมูลไม่พอ ให้ตอบ structured abstention พร้อมสิ่งที่ควรตรวจเพิ่ม
- Acceptance gates:
	- เคสคล้าย `qb_003`, `qb_015` ต้องผ่าน 100%
	- error tag `context_conflict` ใน curriculum ลดลงอย่างมีนัยสำคัญ

### Workstream C: Regulations Procedural/Verification Schema (P1)

- เป้าหมาย: จาก fact-only ไปสู่ workflow-complete
- บังคับ schema ขั้นต่ำ:
	- `ทำได้/ไม่ได้`
	- `เงื่อนไข`
	- `ขั้นตอน`
	- `ผู้ติดต่อ/เอกสาร (ถ้ามี)`
- เพิ่ม repair policy หลัง generation:
	- ถ้า slot ขาด ให้ repair รอบเดียวก่อนส่งคำตอบ
- Acceptance gates:
	- regulation procedural cases: avg missing slots after <= 0.2
	- ลด incomplete tags ใน regulations อย่างน้อย 40%

### Workstream D: General Unanswerable/Refusal Alignment (P1)

- เป้าหมาย: ให้เคส unanswerable ผ่านตาม evaluator template
- กติกา policy:
	- ใช้ refusal template มาตรฐานเดียวกันทุกโดเมนเมื่อหลักฐานไม่พอ
	- ตัดสิน citation policy ให้ชัดในเคส no-evidence (ไม่อ้างแบบผิดบริบท)
	- ถ้าเจอ conflict ให้รายงานว่าไม่สามารถยืนยันได้จากเอกสารที่มี
- Acceptance gates:
	- general overall pass > 0.30 ระยะแรก
	- `context_conflict` ใน general ลดลงอย่างน้อย 50%

## 2-Sprint Delivery Plan

### Sprint 1 (Stabilize P0)

- ส่ง Announcements Router v2 + Curriculum Exact-Code Guard
- รัน targeted eval เฉพาะ 4 task families
- เป้าหมายรวม: overall pass >= 0.40 โดยไม่ลด retrieval/citation

### Sprint 2 (Scale P1)

- ส่ง Regulations procedural schema + General unanswerable alignment
- เปิด repair coverage ใน task family ที่ตอนนี้ยังไม่ attempt
- เป้าหมายรวม: overall pass >= 0.50 และลด incomplete tag ทั้งระบบ >= 45%

## KPI Dashboard ที่ต้องตามรอบถัดไป

- Primary:
	- overall_pass_rate
	- answer_hit_rate
	- retrieve_found_but_answer_incomplete (count และ per-domain)
- Guardrail:
	- retrieval_hit_rate (ต้องไม่ตกเกิน 2 จุด)
	- citation_validity_rate (ต้อง >= 0.90)
	- runtime_error_rate (ต้องคงที่ที่ 0)

## One-line Executive Summary

- ระบบตอนนี้หาเจอแต่ตอบไม่เป็นในโจทย์จริงแบบเปิดกว้าง; รอบถัดไปต้องลงทุนที่ intent routing, abstention, และ procedural answer shaping ไม่ใช่ retriever tuning
