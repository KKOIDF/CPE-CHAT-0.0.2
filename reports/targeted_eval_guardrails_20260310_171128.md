# Targeted Eval targeted_eval_guardrails_20260310_171128

## ann_exact_date_guardrail [PASS]
- domain: announcements
- latency_ms: 2962.2
- contexts: 8
- source_hit: True
- abstain_hit: True
- sources: eng2561.txt, ประกาศ_มจธ_หลักเกณฑ์การจัดสรรผลประโยชน์_พศ2566_ฉบับเต็ม.txt, insurance_std_1.txt, insurance_std.txt
- question: ประกาศค่าประกันภัยมีผลบังคับตั้งแต่วันที่เท่าไร
- answer: ไม่พบข้อความยืนยันโดยตรงในเอกสารที่ค้นได้

## ann_accident_insurance_fee [FAIL]
- domain: announcements
- latency_ms: 4278.8
- contexts: 8
- source_hit: True
- abstain_hit: True
- sources: insurance_std_1.txt, 131.txt, insurance_std.txt, 137.txt, 2018_06_08_15_13_16.txt
- question: มหาวิทยาลัยเก็บค่าประกันภัยอุบัติเหตุคืออะไร?
- answer: ไม่พบข้อความยืนยันโดยตรงในเอกสารที่ค้นได้

## reg_conflict_priority [FAIL]
- domain: regulations
- latency_ms: 4401.5
- contexts: 8
- source_hit: True
- abstain_hit: True
- sources: forms.txt, 129.txt, rule_exam2560.txt
- question: ถ้าข้อความในระเบียบอื่นขัดกับระเบียบการสอบจะให้ใช้เอกสารไหน?
- answer: ไม่พบข้อความยืนยันโดยตรงในเอกสารที่ค้นได้

## cur_total_credits [PASS]
- domain: curriculum
- latency_ms: 3.9
- contexts: 0
- source_hit: True
- abstain_hit: False
- question: หลักสูตรวิศวกรรมคอมพิวเตอร์ต้องศึกษารวมกี่หน่วยกิต?
- answer: - หลักสูตรวิศวกรรมคอมพิวเตอร์ต้องศึกษารวม 130 หน่วยกิต [FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt/1]
- ข้อความอ้างอิงคือ จำนวนหน่วยกิตที่เรียนตลอดหลักสูตร 130 หน่วยกิต [FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt/1]

## cur_cpe100_lookup [FAIL]
- domain: curriculum
- latency_ms: 3.8
- contexts: 0
- source_hit: False
- abstain_hit: False
- question: วิชา CPE 100 คืออะไร และมีกี่หน่วยกิต?
- answer: - วิชา CPE 100 คือ การเขียนโปรแกรมคอมพิวเตอร์สำหรับวิศวกร [FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt/1]
- วิชา CPE 100 มีจำนวน 3 หน่วยกิต [FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt/1]
