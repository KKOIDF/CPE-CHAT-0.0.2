# Targeted Eval targeted_eval_guardrails_20260310_165849

## ann_exact_date_guardrail [PASS]
- domain: announcements
- latency_ms: 2329.1
- contexts: 8
- source_hit: True
- abstain_hit: True
- sources: eng2561.txt, ประกาศ_มจธ_หลักเกณฑ์การจัดสรรผลประโยชน์_พศ2566_ฉบับเต็ม.txt, insurance_std_1.txt, insurance_std.txt
- question: ประกาศค่าประกันภัยมีผลบังคับตั้งแต่วันที่เท่าไร
- answer: - ประกาศค่าประกันภัยมีผลบังคับใช้ตั้งแต่ปีการศึกษา 2563 เป็นต้นไป
- เอกสารไม่ได้กล่าวตรง ๆ เกี่ยวกับวันที่แน่นอนในแต่ละเดือนหรือวันถัดจากวันประกาศสำหรับประกาศค่าประกันภัย โดยข้อมูลที่มีระบุเพียงว่า "ตั้งแต่ปีการศึกษา 2563 เป็นต้นไป"

## ann_registered_foreign_fee [FAIL]
- domain: announcements
- latency_ms: 1953.9
- contexts: 8
- source_hit: True
- abstain_hit: False
- sources: t_fee.txt, 131.txt, fee2567update.txt, announce_financ.txt
- question: ค่าจัดส่งต่างประเทศแบบลงทะเบียนเท่าไร?
- answer: - ค่าจัดส่งต่างประเทศแบบลงทะเบียน (Registered) สำหรับเอกสารสำคัญทางการศึกษา คือ 200 บาท ตามประกาศอัตราค่าธรรมเนียมการบริการจัดส่งเอกสารสำคัญทางการศึกษาทางไปรษณีย์ พ.ศ. 2562

## reg_conflict_priority [PASS]
- domain: regulations
- latency_ms: 3425.0
- contexts: 8
- source_hit: True
- abstain_hit: False
- sources: forms.txt, 129.txt, rule_exam2560.txt
- question: ถ้าข้อความในระเบียบอื่นขัดกับระเบียบการสอบจะให้ใช้เอกสารไหน?
- answer: - ระเบียบการสอบของนักศึกษา พ.ศ. 2560 ให้ใช้แทนเอกสารอื่นที่ขัดหรือแย้งกับระเบียบนี้
- ข้อ 4 ของระเบียบการสอบ พ.ศ. 2560 ระบุชัดเจนว่า "ข้อความในระเบียบมติประกาศหรือคำสั่งอื่นใดซึ่งขัดหรือแย้งกับระเบียบนี้ให้ใช้ระเบียบนี้แทน"
- ดังนั้น หากข้อความในระเบียบอื่นขัดกับระเบียบการสอบ จะให้ใช้ "ระเบียบมหาวิทยาลัยเทคโนโลยีพระจอมเกล้าธนบุรีว่าด้วยการสอบของนักศึกษา พ.ศ. 2560" เป็นหลัก

## cur_total_credits [FAIL]
- domain: curriculum
- latency_ms: 90060.8
- contexts: 0
- source_hit: False
- abstain_hit: False
- error: ReadTimeout: HTTPConnectionPool(host='127.0.0.1', port=8001): Read timed out. (read timeout=90.0)
- question: หลักสูตรวิศวกรรมคอมพิวเตอร์ต้องศึกษารวมกี่หน่วยกิต?
- answer: 

## cur_cpe100_lookup [FAIL]
- domain: curriculum
- latency_ms: 90064.5
- contexts: 0
- source_hit: False
- abstain_hit: False
- error: ReadTimeout: HTTPConnectionPool(host='127.0.0.1', port=8001): Read timed out. (read timeout=90.0)
- question: วิชา CPE 100 คืออะไร และมีกี่หน่วยกิต?
- answer:
