# Targeted Eval targeted_eval_guardrails_20260310_193044

## ann_exact_date_guardrail [PASS]
- domain: announcements
- latency_ms: 2920.6
- contexts: 8
- source_hit: True
- abstain_hit: True
- sources: eng2561.txt, ประกาศ_มจธ_หลักเกณฑ์การจัดสรรผลประโยชน์_พศ2566_ฉบับเต็ม.txt, insurance_std_1.txt, insurance_std.txt
- question: ประกาศค่าประกันภัยมีผลบังคับตั้งแต่วันที่เท่าไร
- answer: ไม่พบข้อความยืนยันวันหรือวันที่ที่ถามโดยตรงในเอกสารที่ค้นได้

## ann_accident_insurance_fee [PASS]
- domain: announcements
- latency_ms: 3102.9
- contexts: 8
- source_hit: True
- abstain_hit: True
- sources: insurance_std_1.txt, 131.txt, insurance_std.txt, 137.txt, 2018_06_08_15_13_16.txt
- question: มหาวิทยาลัยเก็บค่าประกันภัยอุบัติเหตุคืออะไร?
- answer: - มหาวิทยาลัยเทคโนโลยีพระจอมเกล้าธนบุรีเก็บค่าประกันภัยอุบัติเหตุจากนักศึกษา年人ละ 500 บาทต่อปีการศึกษา
- ข้อมูลนี้มาจากข้อ 4 ในเอกสาร และ ซึ่งระบุชัดเจนว่าเป็นอัตราการจัดเก็บต่อปีการศึกษาต่อคน
- เอกสารไม่ได้กล่าวตรง ๆ เกี่ยวกับรายละเอียดเพิ่มเติม เช่น ครอบคลุมความคุ้มครองประเภทใด หรือระยะเวลาคุ้มครอง แต่ยืนยันว่ามีการเก็บค่าประกันภัยอุบัติเหตุปีละ 500 บาทต่อคน

## ann_insurance_fee_per_year [PASS]
- domain: announcements
- latency_ms: 2503.3
- contexts: 8
- source_hit: True
- abstain_hit: False
- sources: insurance_std_1.txt, 131.txt, insurance_std.txt
- question: นักศึกษาต้องจ่ายค่าประกันภัยเท่าไรต่อปี?
- answer: - นักศึกษาต้องจ่ายค่าประกันภัยอุบัติเหตุ 500 บาทต่อปีการศึกษา
- ข้อมูลนี้มาจากข้อ 4 ในเอกสาร และ ซึ่งระบุชัดเจนว่าอัตราการจัดเก็บค่าประกันภัยอุบัติเหตุจากนักศึกษาคือ 500 บาทต่อคนต่อปีการศึกษา

## reg_conflict_priority [PASS]
- domain: regulations
- latency_ms: 5146.7
- contexts: 8
- source_hit: True
- abstain_hit: False
- sources: forms.txt, 129.txt, rule_exam2560.txt
- question: ถ้าข้อความในระเบียบอื่นขัดกับระเบียบการสอบจะให้ใช้เอกสารไหน?
- answer: - ระเบียบการสอบของนักศึกษาพ.ศ. 2560 ระบุชัดเจนว่า ข้อความในระเบียบ คำสั่ง ประกาศ หรือมติอื่นใดที่ขัดหรือแย้งกับระเบียบนี้ ให้ใช้ระเบียบการสอบของนักศึกษาพ.ศ. 2560 แทน
- ข้อ 4 ของระเบียบการสอบพ.ศ. 2560 ระบุว่า “ข้อความในระเบียบมติประกาศหรือคำสั่งอื่นใดซึ่งขัดหรือแย้งกับระเบียบนี้ให้ใช้ระเบียบนี้แทน”
- ดังนั้น หากข้อความในระเบียบอื่นขัดกับระเบียบการสอบ จะให้ใช้ “ระเบียบมหาวิทยาลัยเทคโนโลยีพระจอมเกล้าธนบุรีว่าด้วยการสอบของนักศึกษาพ.ศ. 2560” เป็นหลักปฏิบัติ

## reg_repeal_old_rule [PASS]
- domain: regulations
- latency_ms: 5632.9
- contexts: 8
- source_hit: True
- abstain_hit: True
- sources: 129.txt, celemony2539.txt, rule57_2.txt, 135.txt, rule_exam2560.txt
- question: ระเบียบการสอบใหม่ยกเลิกระเบียบเก่าอะไร?
- answer: - ระเบียบการสอบใหม่ยกเลิกข้อความในข้อ 26 แห่งระเบียบมหาวิทยาลัยเทคโนโลยีพระจอมเกล้าธนบุรีว่าด้วยการศึกษาระดับปริญญาตรี พ.ศ. 2557
- ระเบียบฉบับนี้มีผลบังคับใช้ตั้งแต่วันที่ประกาศ 12 กรกฎาคม พ.ศ. 2539
- ข้อความที่ยกเลิกเกี่ยวข้องกับการวัดผลการศึกษาแต่ละรายวิชาหรือกลุ่มวิชา โดยเฉพาะการกำหนดระดับคะแนนตัวอักษรและเงื่อนไขการให้ผลการศึกษา
- ระเบียบฉบับใหม่ให้ใช้ข้อความที่แก้ไขแล้วแทน ซึ่งระบุรายละเอียดเกี่ยวกับระดับคะแนน ความหมาย และเงื่อนไขการให้ผลการศึกษาอย่างชัดเจน
- เอกสารไม่ได้กล่าวตรง ๆ ว่าระเบียบการสอบฉบับเก่าที่ยกเลิกมีชื่อเต็มว่าอะไร แต่ระบุว่าเป็น "ข้อ 26 แห่งระเบียบมหาวิทยาลัยเทคโนโลยีพระจ

## cur_total_credits [PASS]
- domain: curriculum
- latency_ms: 3.7
- contexts: 0
- source_hit: True
- abstain_hit: False
- answer_sources: FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt
- question: หลักสูตรวิศวกรรมคอมพิวเตอร์ต้องศึกษารวมกี่หน่วยกิต?
- answer: - หลักสูตรวิศวกรรมคอมพิวเตอร์ต้องศึกษารวม 130 หน่วยกิต [FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt/1]
- ข้อความอ้างอิงคือ จำนวนหน่วยกิตที่เรียนตลอดหลักสูตร 130 หน่วยกิต [FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt/1]

## cur_cpe100_lookup [PASS]
- domain: curriculum
- latency_ms: 3.4
- contexts: 0
- source_hit: True
- abstain_hit: False
- answer_sources: FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt
- question: วิชา CPE 100 คืออะไร และมีกี่หน่วยกิต?
- answer: - วิชา CPE 100 คือ การเขียนโปรแกรมคอมพิวเตอร์สำหรับวิศวกร [FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt/1]
- วิชา CPE 100 มีจำนวน 3 หน่วยกิต [FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt/1]

## cur_cpe101_lookup [PASS]
- domain: curriculum
- latency_ms: 3.2
- contexts: 0
- source_hit: True
- abstain_hit: False
- answer_sources: FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt
- question: วิชา CPE 101 คืออะไร และมีกี่หน่วยกิต?
- answer: - วิชา CPE 101 คือ เปิดโลกวิศวกรรมศาสตร์ [FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt/1]
- วิชา CPE 101 มีจำนวน 3 หน่วยกิต [FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt/1]

## cur_cpe111_lookup [PASS]
- domain: curriculum
- latency_ms: 3.2
- contexts: 0
- source_hit: True
- abstain_hit: False
- answer_sources: FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt
- question: วิชา CPE 111 คืออะไร และมีกี่หน่วยกิต?
- answer: - วิชา CPE 111 คือ คณิตศาสตร์ดิสครีตสำหรับวิศวกรคอมพิวเตอร์ [FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt/1]
- วิชา CPE 111 มีจำนวน 3 หน่วยกิต [FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt/1]

## cur_cpe112_lookup [PASS]
- domain: curriculum
- latency_ms: 3.7
- contexts: 0
- source_hit: True
- abstain_hit: False
- answer_sources: FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt
- question: วิชา CPE 112 คืออะไร และมีกี่หน่วยกิต?
- answer: - วิชา CPE 112 คือ การเขียนโปรแกรมด้วยโครงสร้างข้อมูล [FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt/1]
- วิชา CPE 112 มีจำนวน 3 หน่วยกิต [FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt/1]

## cur_cpe121_lookup [PASS]
- domain: curriculum
- latency_ms: 3.5
- contexts: 0
- source_hit: True
- abstain_hit: False
- answer_sources: FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt
- question: วิชา CPE 121 คืออะไร และมีกี่หน่วยกิต?
- answer: - วิชา CPE 121 คือ พื้นฐานวงจรไฟฟ้าและอิเล็กทรอนิกส์ [FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt/1]
- วิชา CPE 121 มีจำนวน 3 หน่วยกิต [FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt/1]

## cur_mth101_lookup [PASS]
- domain: curriculum
- latency_ms: 3.5
- contexts: 0
- source_hit: True
- abstain_hit: False
- answer_sources: FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt
- question: วิชา MTH 101 คืออะไร และมีกี่หน่วยกิต?
- answer: - วิชา MTH 101 คือ คณิตศาสตร์ 1 [FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt/1]
- วิชา MTH 101 มีจำนวน 3 หน่วยกิต [FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt/1]

## cur_phy103_lookup [PASS]
- domain: curriculum
- latency_ms: 3.7
- contexts: 0
- source_hit: True
- abstain_hit: False
- answer_sources: FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt
- question: วิชา PHY 103 คืออะไร และมีกี่หน่วยกิต?
- answer: - วิชา PHY 103 คือ ฟิสิกส์ทั่วไปสำหรับนักศึกษาวิศวกรรมศาสตร์ 1 [FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt/1]
- วิชา PHY 103 มีจำนวน 3 หน่วยกิต [FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt/1]
