# Course-code A/B eval

- json: /home/testuser/CPE-CHAT-0.0.2/reports/course_code_ab_eval_20260320_182016.json
- duration_sec: 114.531

## Summary

- hit_top1_rate: before=0.833 after=1.000 delta=+0.167
- hit_top3_rate: before=0.833 after=1.000 delta=+0.167
- hit_top5_rate: before=0.833 after=1.000 delta=+0.167
- hit_top1_loose_rate: before=0.833 after=1.000 delta=+0.167
- hit_top3_loose_rate: before=0.833 after=1.000 delta=+0.167
- hit_top5_loose_rate: before=0.833 after=1.000 delta=+0.167
- hit_prompt_loose_rate: before=1.000 after=1.000 delta=+0.000
- answer_has_code_rate: before=1.000 after=1.000 delta=+0.000
- non_fallback_rate: before=1.000 after=1.000 delta=+0.000
- structured_answer_rate: before=0.000 after=0.000 delta=+0.000

## After per-question

- Q: CPE 342 คือวิชาอะไร
  hit@1=True hit@3=True hit@5=True loose@5=True prompt_hit=True answer_has_code=True fallback=False structured=False
  top1=foe10_วศ_บ_วิศวกรรมคอมพิวเตอร์_2564.txt/1
  answer=- CPE 342 คือวิชา "การเรียนรู้ของเครื่อง 3"
- มีหน่วยกิต 3 หน่วยกิต โดยมีโครงสร้างชั่วโมงเรียน 2-2-6 (ทฤษฎี 2 ชั่วโมง, ปฏิบัติ 2 ชั่วโมง, งานอิสระ 6 ชั่วโมงต่อสัปดาห์)
- เนื้อหาหลักประกอบด้วย: พื้นฐาน

- Q: LNG 220 คือวิชาอะไร
  hit@1=True hit@3=True hit@5=True loose@5=True prompt_hit=True answer_has_code=True fallback=False structured=False
  top1=foe10_วศ_บ_วิศวกรรมคอมพิวเตอร์_2564.txt/1
  answer=- LNG 220 คือวิชา "ภาษาอังกฤษเชิงวิชาการ 3"
- รหัสวิชา: LNG 220
- ชื่ออังกฤษ: Academic English
- จำนวนหน่วยกิต: 3 (3-0-6)
- วิชาบังคับก่อน: LNG 120 General English หรือได้รับการยกเว้นไม่ต้องเรียนวิชา


- Q: GEN 121 คือวิชาอะไร
  hit@1=True hit@3=True hit@5=True loose@5=True prompt_hit=True answer_has_code=True fallback=False structured=False
  top1=foe10_วศ_บ_วิศวกรรมคอมพิวเตอร์_2564.txt/1
  answer=- GEN 121 คือวิชา "ทักษะการเรียนรู้และการแก้ปัญหา" (Learning and Problem Solving Skills)
- เป็นวิชาศึกษาทั่วไปกลุ่มวิชาการคิดอย่างมีระบบ
- จำนวนหน่วยกิต: 3 หน่วยกิต (3-0-6)
- เนื้อหาหลัก: พัฒนาการเรีย

- Q: CPE 342 อยู่ปีไหน
  hit@1=True hit@3=True hit@5=True loose@5=True prompt_hit=True answer_has_code=True fallback=False structured=False
  top1=foe10_วศ_บ_วิศวกรรมคอมพิวเตอร์_2564.txt/1
  answer=- CPE 342 เป็นรายวิชาในระดับชั้นปีที่ 3
- มีการกล่าวถึง CPE 342 ในบริบทว่าเป็นรายวิชาที่มีชื่อว่า "การเรียนรู้ของเครื่อง 3" หรือ "ภาษาโปรแกรมจาวา 3 หน่วยกิต" ซึ่งอยู่ในหลักสูตรปริญญาตรีสาขาวิศวกรรมคอม

- Q: LNG 220 อยู่กลุ่มวิชาอะไร
  hit@1=True hit@3=True hit@5=True loose@5=True prompt_hit=True answer_has_code=True fallback=False structured=False
  top1=foe10_วศ_บ_วิศวกรรมคอมพิวเตอร์_2564.txt/1
  answer=- LNG 220 อยู่ในกลุ่มวิชาภาษาอังกฤษ
- วิชานี้มีชื่อว่า "ภาษาอังกฤษเชิงวิชาการ 3 (Academic English)"
- เป็นวิชาบังคับในหลักสูตรปรับปรุง พ.ศ. 2564 ของสาขาวิชาวิศวกรรมคอมพิวเตอร์
- อยู่ในชั้นปีที่ 1 ภาคก

- Q: GEN 121 มีกี่หน่วยกิต
  hit@1=True hit@3=True hit@5=True loose@5=True prompt_hit=True answer_has_code=True fallback=False structured=False
  top1=วศ_บ_วศวกรรมคอมพวเตอร_ปรบปรง_64.txt/1
  answer=- GEN 121 มี 3 หน่วยกิต
- ข้อมูลนี้ยืนยันจากหลายแหล่งในบริบท เช่น รายการรายวิชาในภาคการศึกษาที่ 2 ชั้นปีที่ 1 และคำอธิบายรายวิชาที่ระบุ "3(3-0-6)" ซึ่งแสดงว่ามีหน่วยกิตทั้งหมด 3 หน่วยกิต
