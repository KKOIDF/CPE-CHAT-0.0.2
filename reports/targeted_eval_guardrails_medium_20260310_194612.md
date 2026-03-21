# Targeted Eval targeted_eval_guardrails_medium_20260310_194612

## ann_exact_date_guardrail [PASS]
- domain: announcements
- latency_ms: 2223.9
- contexts: 8
- source_hit: True
- abstain_hit: True
- sources: eng2561.txt, ประกาศ_มจธ_หลักเกณฑ์การจัดสรรผลประโยชน์_พศ2566_ฉบับเต็ม.txt, insurance_std_1.txt, insurance_std.txt
- question: ประกาศค่าประกันภัยมีผลบังคับตั้งแต่วันที่เท่าไร
- answer: ไม่พบข้อความยืนยันวันหรือวันที่ที่ถามโดยตรงในเอกสารที่ค้นได้

## ann_accident_insurance_fee [PASS]
- domain: announcements
- latency_ms: 3827.8
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
- latency_ms: 2317.8
- contexts: 8
- source_hit: True
- abstain_hit: False
- sources: insurance_std_1.txt, 131.txt, insurance_std.txt
- question: นักศึกษาต้องจ่ายค่าประกันภัยเท่าไรต่อปี?
- answer: - นักศึกษาต้องจ่ายค่าประกันภัยอุบัติเหตุ 500 บาทต่อปีการศึกษา
- เอกสารระบุชัดเจนว่าอัตราการจัดเก็บค่าประกันภัยอุบัติเหตุจากนักศึกษาคือ 500 บาทต่อคนต่อปีการศึกษา
- ไม่มีข้อความยืนยันโดยตรงว่ามีการเปลี่ยนแปลงอัตราค่าประกันภัยในปีหลังจากที่ข้อมูลนี้ถูกเผยแพร่

## reg_conflict_priority [PASS]
- domain: regulations
- latency_ms: 3504.4
- contexts: 8
- source_hit: True
- abstain_hit: False
- sources: forms.txt, 129.txt, rule_exam2560.txt
- question: ถ้าข้อความในระเบียบอื่นขัดกับระเบียบการสอบจะให้ใช้เอกสารไหน?
- answer: - ระเบียบการสอบของนักศึกษาพ.ศ. 2560 ระบุชัดเจนว่า ข้อความในระเบียบ คำสั่ง ประกาศ หรือมติอื่นใดที่ขัดหรือแย้งกับระเบียบนี้ ให้ใช้ระเบียบนี้แทน
- ดังนั้น หากข้อความในระเบียบอื่นขัดกับระเบียบการสอบ จะให้ใช้ "ระเบียบมหาวิทยาลัยเทคโนโลยีพระจอมเกล้าธนบุรีว่าด้วยการสอบของนักศึกษาพ.ศ. 2560" แทน
- เอกสารที่ใช้เป็นหลักคือ ระเบียบการสอบ พ.ศ. 2560 ตามข้อ 4 ของระเบียบนี้

## reg_repeal_old_rule [PASS]
- domain: regulations
- latency_ms: 5421.1
- contexts: 8
- source_hit: True
- abstain_hit: True
- sources: 129.txt, celemony2539.txt, rule57_2.txt, 135.txt, rule_exam2560.txt
- question: ระเบียบการสอบใหม่ยกเลิกระเบียบเก่าอะไร?
- answer: - ระเบียบการสอบใหม่ยกเลิกข้อความในข้อ 26 แห่งระเบียบมหาวิทยาลัยเทคโนโลยีพระจอมเกล้าธนบุรีว่าด้วยการศึกษาระดับปริญญาตรี พ.ศ. 2557
- ระเบียบฉบับนี้มีผลบังคับใช้ตั้งแต่วันที่ประกาศ 12 กรกฎาคม พ.ศ. 2539
- ข้อความที่ยกเลิกเกี่ยวข้องกับการวัดผลการศึกษาแต่ละรายวิชาหรือกลุ่มวิชา โดยเฉพาะการกำหนดระดับคะแนนตัวอักษรและนิยามของแต่ละระดับ
- ระเบียบฉบับใหม่ให้ใช้ข้อความที่แก้ไขแล้วแทน ซึ่งระบุรายละเอียดเกี่ยวกับระดับคะแนน แต้มคะแนน และความหมายของแต่ละระดับอย่างชัดเจน
- ระเบียบฉบับนี้ไม่ได้กล่าวตรง ๆ ว่ายกเลิกระเบียบอื่นนอกเหนือจากข้อ 26 แห่งระเบียบ พ.ศ. 2557 ที่ระบุไว้ในข้อ 6

## cur_total_credits [PASS]
- domain: curriculum
- latency_ms: 3.9
- contexts: 0
- source_hit: True
- abstain_hit: False
- answer_sources: FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt
- question: หลักสูตรวิศวกรรมคอมพิวเตอร์ต้องศึกษารวมกี่หน่วยกิต?
- answer: - หลักสูตรวิศวกรรมคอมพิวเตอร์ต้องศึกษารวม 130 หน่วยกิต [FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt/1]
- ข้อความอ้างอิงคือ จำนวนหน่วยกิตที่เรียนตลอดหลักสูตร 130 หน่วยกิต [FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt/1]

## cur_cpe100_lookup [PASS]
- domain: curriculum
- latency_ms: 3.5
- contexts: 0
- source_hit: True
- abstain_hit: False
- answer_sources: FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt
- question: วิชา CPE 100 คืออะไร และมีกี่หน่วยกิต?
- answer: - วิชา CPE 100 คือ การเขียนโปรแกรมคอมพิวเตอร์สำหรับวิศวกร [FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt/1]
- วิชา CPE 100 มีจำนวน 3 หน่วยกิต [FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt/1]

## cur_cpe101_lookup [PASS]
- domain: curriculum
- latency_ms: 3.3
- contexts: 0
- source_hit: True
- abstain_hit: False
- answer_sources: FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt
- question: วิชา CPE 101 คืออะไร และมีกี่หน่วยกิต?
- answer: - วิชา CPE 101 คือ เปิดโลกวิศวกรรมศาสตร์ [FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt/1]
- วิชา CPE 101 มีจำนวน 3 หน่วยกิต [FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt/1]

## cur_cpe111_lookup [PASS]
- domain: curriculum
- latency_ms: 3.4
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
- latency_ms: 3.6
- contexts: 0
- source_hit: True
- abstain_hit: False
- answer_sources: FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt
- question: วิชา CPE 121 คืออะไร และมีกี่หน่วยกิต?
- answer: - วิชา CPE 121 คือ พื้นฐานวงจรไฟฟ้าและอิเล็กทรอนิกส์ [FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt/1]
- วิชา CPE 121 มีจำนวน 3 หน่วยกิต [FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt/1]

## cur_mth101_lookup [PASS]
- domain: curriculum
- latency_ms: 3.3
- contexts: 0
- source_hit: True
- abstain_hit: False
- answer_sources: FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt
- question: วิชา MTH 101 คืออะไร และมีกี่หน่วยกิต?
- answer: - วิชา MTH 101 คือ คณิตศาสตร์ 1 [FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt/1]
- วิชา MTH 101 มีจำนวน 3 หน่วยกิต [FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt/1]

## cur_phy103_lookup [PASS]
- domain: curriculum
- latency_ms: 3.6
- contexts: 0
- source_hit: True
- abstain_hit: False
- answer_sources: FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt
- question: วิชา PHY 103 คืออะไร และมีกี่หน่วยกิต?
- answer: - วิชา PHY 103 คือ ฟิสิกส์ทั่วไปสำหรับนักศึกษาวิศวกรรมศาสตร์ 1 [FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt/1]
- วิชา PHY 103 มีจำนวน 3 หน่วยกิต [FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt/1]

## ann_insurance_decider [PASS]
- domain: announcements
- latency_ms: 5038.0
- contexts: 8
- source_hit: True
- abstain_hit: False
- sources: eng2561.txt, 137.txt, 139.txt, fee2567update.txt, 2018_06_08_15_13_16.txt
- question: ใครมีอำนาจวินิจฉัยเมื่อเกิดปัญหากับประกาศนี้?
- answer: - อธิการบดีมีอำนาจวินิจฉัยเมื่อเกิดปัญหากับประกาศนี้
- เอกสารระบุชัดเจนว่า ในกรณีมีข้อขัดแย้ง ข้อขัดหรือแย้ง หรือปัญหาเกี่ยวกับการดำเนินการ อธิการบดีเป็นผู้วินิจฉัยชี้ขาด
- คำวินิจฉัยหรือคำสั่งของอธิการบดีถือเป็นที่สุด
- ข้อความดังกล่าวปรากฏในหลายประกาศ เช่น ข้อ 5 จาก eng2561.txt/1, ข้อ 6 จาก fee2567update.txt/1 และข้อ 9 จาก 2018_06_08_15_13_16.txt/1 โดยมีความสอดคล้องกัน
- ดังนั้น คำตอบที่สรุปได้จากบริบทคือ อธิการบดีมีอำนาจวินิจฉัยปัญหาที่เกิดขึ้นกับประกาศนี้

## ann_postal_title [PASS]
- domain: announcements
- latency_ms: 2120.7
- contexts: 8
- source_hit: True
- abstain_hit: False
- sources: t_fee.txt, fee2567update.txt, announce_financ.txt, insurance_std_1.txt, insurance_std.txt
- question: ประกาศค่าธรรมเนียมการจัดส่งเอกสารมีชื่ออะไร?
- answer: - ประกาศค่าธรรมเนียมการจัดส่งเอกสารมีชื่อว่า “ประกาศมหาวิทยาลัยเทคโนโลยีพระจอมเกล้าธนบุรีเรื่องอัตราค่าธรรมเนียมการบริการจัดส่งเอกสารสำคัญทางการศึกษาทางไปรษณีย์พ.ศ. 2562”

## ann_postal_collector [PASS]
- domain: announcements
- latency_ms: 1281.0
- contexts: 8
- source_hit: True
- abstain_hit: False
- sources: t_fee.txt, announce_financ.txt
- question: ใครเป็นผู้เรียกเก็บค่าธรรมเนียมการจัดส่งเอกสาร?
- answer: - สำนักงานทะเบียนนักศึกษาเป็นผู้ดำเนินการเรียกเก็บค่าธรรมเนียมในการจัดส่งเอกสารสำคัญทางการศึกษาเป็นรายครั้ง

## reg_exam_dress [PASS]
- domain: regulations
- latency_ms: 3612.5
- contexts: 8
- source_hit: True
- abstain_hit: True
- sources: forms.txt, rule_exam2560.txt
- question: นักศึกษาต้องแต่งตัวแบบไหนเมื่อเข้าห้องสอบ?
- answer: - นักศึกษาต้องแต่งกายด้วยชุดนักศึกษาที่ถูกต้องตามข้อบังคับมหาวิทยาลัยเทคโนโลยีพระจอมเกล้าธนบุรีว่าด้วยเครื่องแต่งกายนักศึกษา
- เอกสารไม่ได้กล่าวตรง ๆ ว่า "ชุดนักศึกษา" หมายถึงชุดแบบใดโดยเฉพาะ (เช่น ชุดนักศึกษาภาคปกติ ชุดนักศึกษาภาคพิเศษ หรือชุดเฉพาะคณะ)
- ไม่มีข้อความยืนยันโดยตรงในบริบทเกี่ยวกับรายละเอียดของชุด เช่น สี รูปแบบ หรือประเภทเสื้อผ้าที่อนุญาต

## reg_exam_bring_id [PASS]
- domain: regulations
- latency_ms: 5640.0
- contexts: 8
- source_hit: True
- abstain_hit: True
- sources: rule_exam2560.txt
- question: นักศึกษาต้องนำสิ่งของอะไรเข้าห้องสอบ?
- answer: - นักศึกษาต้องนำบัตรนักศึกษาหรือใบแทนบัตรประจำตัวนักศึกษาเข้าห้องสอบ
- นักศึกษาอาจนำเครื่องคำนวณเข้าห้องสอบได้เฉพาะกรณีที่อาจารย์ประจำวิชาอนุญาต และต้องเป็นรุ่นที่มหาวิทยาลัยกำหนด โดยต้องผ่านการตรวจสอบและติดสติกเกอร์จากสำนักงานทะเบียนนักศึกษาแล้ว
- นักศึกษาไม่สามารถนำเอกสาร ไม้บรรทัดที่มีสูตร หรืออุปกรณ์อิเล็กทรอนิกส์อื่นใดที่มีคุณสมบัติคล้ายเครื่องคำนวณเข้าห้องสอบ เว้นแต่ได้รับอนุญาตจากอาจารย์ผู้สอน
- นักศึกษาไม่สามารถนำเครื่องมือสื่อสารหรืออุปกรณ์อิเล็กทรอนิกส์ทุกชนิดเข้าห้องสอบ เว้นแต่เป็นอุปกรณ์พิเศษทางการแพทย์ เช่น เครื่องช่วยฟัง
- ระเบียบไม่ได้กล่าวตรง ๆ เกี่ยวกับการนำสิ่งของอื่น ๆ เข้าห

## reg_exam_calculator [PASS]
- domain: regulations
- latency_ms: 3797.8
- contexts: 8
- source_hit: True
- abstain_hit: True
- sources: forms.txt, rule_exam2560.txt, handbook2562g.txt
- question: นักศึกษาเอาเครื่องคิดเลขเข้าห้องสอบได้หรือไม่?
- answer: - นักศึกษา **ห้าม** นำเครื่องคิดเลขเข้าห้องสอบโดยทั่วไป
- ยกเว้นกรณีที่ **อาจารย์ประจำวิชาได้อนุญาตไว้ในข้อสอบรายวิชานั้น**
- หากได้รับอนุญาต ต้องใช้เครื่องคิดเลขรุ่นที่มหาวิทยาลัยกำหนด และต้องนำไปให้สำนักงานทะเบียนนักศึกษาตรวจสอบและติดสติกเกอร์เรียบร้อยแล้ว
- อนุญาตให้นำเข้าได้เพียง **คนละ 1 เครื่องเท่านั้น**
เอกสารไม่ได้กล่าวตรง ๆ ว่าสามารถนำเครื่องคิดเลขเข้าห้องสอบได้โดยไม่มีเงื่อนไข แต่ระบุเงื่อนไขเฉพาะกรณีที่อาจารย์อนุญาตไว้เท่านั้น.

## cur_cpe222_lookup [PASS]
- domain: curriculum
- latency_ms: 2.8
- contexts: 0
- source_hit: True
- abstain_hit: False
- answer_sources: FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt
- question: วิชา CPE 222 คืออะไร และมีกี่หน่วยกิต?
- answer: - วิชา CPE 222 คือ อิเล็กทรอนิกส์ดิจิทัลและการออกแบบวงจรเชิงตรรกะ [FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt/1]
- วิชา CPE 222 มีจำนวน 3 หน่วยกิต [FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt/1]

## cur_cpe231_lookup [PASS]
- domain: curriculum
- latency_ms: 2.5
- contexts: 0
- source_hit: True
- abstain_hit: False
- answer_sources: FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt
- question: วิชา CPE 231 คืออะไร และมีกี่หน่วยกิต?
- answer: - วิชา CPE 231 คือ ขั้นตอนวิธี [FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt/1]
- วิชา CPE 231 มีจำนวน 3 หน่วยกิต [FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt/1]

## cur_cpe232_lookup [PASS]
- domain: curriculum
- latency_ms: 2.4
- contexts: 0
- source_hit: True
- abstain_hit: False
- answer_sources: FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt
- question: วิชา CPE 232 คืออะไร และมีกี่หน่วยกิต?
- answer: - วิชา CPE 232 คือ แบบจำลองข้อมูล [FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt/1]
- วิชา CPE 232 มีจำนวน 3 หน่วยกิต [FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt/1]

## cur_cpe241_lookup [PASS]
- domain: curriculum
- latency_ms: 3.1
- contexts: 0
- source_hit: True
- abstain_hit: False
- answer_sources: FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt
- question: วิชา CPE 241 คืออะไร และมีกี่หน่วยกิต?
- answer: - วิชา CPE 241 คือ ระบบฐานข้อมูล [FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt/1]
- วิชา CPE 241 มีจำนวน 3 หน่วยกิต [FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt/1]

## cur_cpe333_lookup [PASS]
- domain: curriculum
- latency_ms: 2.4
- contexts: 0
- source_hit: True
- abstain_hit: False
- answer_sources: FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt
- question: วิชา CPE 333 คืออะไร และมีกี่หน่วยกิต?
- answer: - วิชา CPE 333 คือ ระบบปฏิบัติการ [FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt/1]
- วิชา CPE 333 มีจำนวน 3 หน่วยกิต [FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt/1]

## cur_cpe334_lookup [PASS]
- domain: curriculum
- latency_ms: 1.7
- contexts: 0
- source_hit: True
- abstain_hit: False
- answer_sources: FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt
- question: วิชา CPE 334 คืออะไร และมีกี่หน่วยกิต?
- answer: - วิชา CPE 334 คือ วิศวกรรมซอฟต์แวร์ [FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt/1]
- วิชา CPE 334 มีจำนวน 3 หน่วยกิต [FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt/1]

## cur_gen101_lookup [PASS]
- domain: curriculum
- latency_ms: 1.7
- contexts: 0
- source_hit: True
- abstain_hit: False
- answer_sources: FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt
- question: วิชา GEN 101 คืออะไร และมีกี่หน่วยกิต?
- answer: - วิชา GEN 101 คือ พลศึกษา [FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt/1]
- วิชา GEN 101 มีจำนวน 1 หน่วยกิต [FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt/1]

## cur_gen111_lookup [PASS]
- domain: curriculum
- latency_ms: 1.6
- contexts: 0
- source_hit: True
- abstain_hit: False
- answer_sources: FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt
- question: วิชา GEN 111 คืออะไร และมีกี่หน่วยกิต?
- answer: - วิชา GEN 111 คือ มนุษย์กับหลักจริยศาสตร์เพื่อการดำเนินชีวิต [FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt/1]
- วิชา GEN 111 มีจำนวน 3 หน่วยกิต [FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt/1]

## cur_gen231_lookup [PASS]
- domain: curriculum
- latency_ms: 1.7
- contexts: 0
- source_hit: True
- abstain_hit: False
- answer_sources: FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt
- question: วิชา GEN 231 คืออะไร และมีกี่หน่วยกิต?
- answer: - วิชา GEN 231 คือ มหัศจรรย์แห่งความคิด [FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt/1]
- วิชา GEN 231 มีจำนวน 3 หน่วยกิต [FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt/1]

## cur_lng223_lookup [PASS]
- domain: curriculum
- latency_ms: 1.6
- contexts: 0
- source_hit: True
- abstain_hit: False
- answer_sources: FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt
- question: วิชา LNG 223 คืออะไร และมีกี่หน่วยกิต?
- answer: - วิชา LNG 223 คือ ภาษาอังกฤษเพื่อการสื่อสารในที่ทำงาน [FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt/1]
- วิชา LNG 223 มีจำนวน 3 หน่วยกิต [FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt/1]

## cur_mth234_lookup [PASS]
- domain: curriculum
- latency_ms: 1.6
- contexts: 0
- source_hit: True
- abstain_hit: False
- answer_sources: FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt
- question: วิชา MTH 234 คืออะไร และมีกี่หน่วยกิต?
- answer: - วิชา MTH 234 คือ พีชคณิตเชิงเส้น [FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt/1]
- วิชา MTH 234 มีจำนวน 3 หน่วยกิต [FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt/1]

## cur_chm103_lookup [PASS]
- domain: curriculum
- latency_ms: 1.7
- contexts: 0
- source_hit: True
- abstain_hit: False
- answer_sources: FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt
- question: วิชา CHM 103 คืออะไร และมีกี่หน่วยกิต?
- answer: - วิชา CHM 103 คือ เคมีพื้นฐาน [FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt/1]
- วิชา CHM 103 มีจำนวน 3 หน่วยกิต [FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt/1]

## cur_sta302_lookup [PASS]
- domain: curriculum
- latency_ms: 1.7
- contexts: 0
- source_hit: True
- abstain_hit: False
- answer_sources: FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt
- question: วิชา STA 302 คืออะไร และมีกี่หน่วยกิต?
- answer: - วิชา STA 302 คือ สถิติสำหรับวิศวกร [FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt/1]
- วิชา STA 302 มีจำนวน 3 หน่วยกิต [FOE10_วศ.บ.วิศวกรรมคอมพิวเตอร์_2564.txt/1]
