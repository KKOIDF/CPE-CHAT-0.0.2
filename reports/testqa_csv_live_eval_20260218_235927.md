# Live CSV Eval Report (20260218_235927)

- input: testQA_domains_30_revised.csv
- base_url: http://127.0.0.1:8001
- questions: 90
- errors: 0
- heuristic passes: 2
- heuristic fails: 88
- ref-hint questions: 26
- ref leaks (should be 0 in strict mode): 5
- numeric mismatches (expected numbers not all present in answer): 87

## Reference-leak cases (top)
- [announcements #1] ref=insurance-std.txt sources=insurance_std.txt, insurance_std.txt, insurance_std.txt, insurance_std.txt, insurance_std.txt, insurance_std.txt, insurance_std.txt, insurance_std.txt
- [announcements #2] ref=insurance-std.txt sources=insurance_std.txt, insurance_std.txt, insurance_std.txt, insurance_std.txt, insurance_std.txt, insurance_std.txt, insurance_std.txt, insurance_std.txt
- [announcements #3] ref=insurance-std.txt sources=insurance_std.txt, insurance_std.txt, insurance_std.txt, insurance_std.txt, insurance_std.txt, insurance_std.txt, insurance_std.txt, insurance_std.txt
- [announcements #4] ref=insurance-std.txt sources=insurance_std.txt, insurance_std.txt, insurance_std.txt, insurance_std.txt, insurance_std.txt, insurance_std.txt, insurance_std.txt, insurance_std.txt
- [announcements #5] ref=insurance-std.txt sources=insurance_std.txt, insurance_std.txt, insurance_std.txt, insurance_std.txt, insurance_std.txt, insurance_std.txt, insurance_std.txt, insurance_std.txt

## Numeric-mismatch cases (top)
- [announcements #5] jaccard=0.00 exp=['5'] ans=[]
- [announcements #7] jaccard=0.00 exp=['2', '2562'] ans=['73', '73', '73', '72']
- [announcements #8] jaccard=0.00 exp=['3'] ans=[]
- [announcements #9] jaccard=0.00 exp=['4'] ans=[]
- [announcements #10] jaccard=0.00 exp=['3.1', '1', '50'] ans=['77', '22', '76', '21']
- [announcements #11] jaccard=0.00 exp=['3.1', '2', '100'] ans=['79', '78', '79']
- [announcements #12] jaccard=0.00 exp=['3.2', '1', '200'] ans=['77', '22', '27', '29']
- [announcements #13] jaccard=0.00 exp=['3.2', '2', '1200'] ans=['79', '24', '79']
- [announcements #14] jaccard=0.00 exp=['3.3', '1', '100'] ans=['22', '21', '22']
- [announcements #15] jaccard=0.00 exp=['3.3', '2', '1000'] ans=['22', '21', '22']
- [announcements #16] jaccard=0.00 exp=['1', '2557'] ans=['2575']
- [announcements #18] jaccard=0.00 exp=['3'] ans=['2575']

## Heuristic fails (top)
### announcements #1
ref: insurance-std.txt | ref_leak=True
q: มหาวิทยาลัยเก็บค่าประกันภัยอุบัติเหตุคืออะไร? (อ้างอิง: insurance-std.txt)
expected: ข้อ 1 ประกาศนี้เรียกว่า "ประกาศมหาวิทยาลัยเทคโนโลยีพระจอมเกล้าธนบุรี เรื่อง "การเก็บค่า ประกันภัยอุบัติเหตุสำหรับนักศึกษา พ.ศ. 2563"
answer: - มหาวิทยาลัยเทคโนโลยีพระจอมเกล้าธนบุรีเก็บค่าประกันภัยอุบัติเหตุจากนักศึกษาคนละ 500 บาทต่อปีการศึกษา - ค่าประกันภัยอุบัติเหตุหมายถึงเงินที่เก็บจากนักศึกษาของมหาวิทยาลัย - การเก็บค่าประกันภัยนี้มีจุดประสงค์เพื่อคุ้มครองสวัสดิภาพของนักศึกษาจากการเกิดอุบัติเห...
sources: insurance_std.txt, insurance_std.txt, insurance_std.txt, insurance_std.txt, insurance_std.txt, insurance_std.txt, insurance_std.txt, insurance_std.txt

### announcements #2
ref: insurance-std.txt | ref_leak=True
q: ประกาศค่าประกันภัยมีผลบังคับตั้งแต่เมื่อไร? (อ้างอิง: insurance-std.txt)
expected: ข้อ 2 ประกาศนี้ให้ใช้บังคับตั้งแต่ปีการศึกษา 2563 เป็นต้นไป
answer: - ประกาศค่าประกันภัยมีผลบังคับใช้ตั้งแต่ปีการศึกษา 2563 เป็นต้นไป - เอกสารไม่ได้กล่าวตรง ๆ ถึงวันที่แน่นอนภายในปีการศึกษา 2563 ที่เริ่มมีผลบังคับใช้ - ข้อมูลจากบริบทระบุว่าประกาศออกในวันที่ 9 เมษายน พ.ศ. 2563 แต่ไม่ได้ระบุว่าเป็นวันที่เริ่มมีผลบังคับใช้ในเช...
sources: insurance_std.txt, insurance_std.txt, insurance_std.txt, insurance_std.txt, insurance_std.txt, insurance_std.txt, insurance_std.txt, insurance_std.txt

### announcements #3
ref: insurance-std.txt | ref_leak=True
q: ใครมีอำนาจเก็บค่าประกันภัยจากนักศึกษา? (อ้างอิง: insurance-std.txt)
expected: ข้อ 3 ในประกาศนี้บัญญัติให้สำนักงานทะเบียนนักศึกษาเป็นผู้ดำเนินการเรียกเก็บค่าประกันภัยอุบัติเหตุจากนักศึกษา
answer: - มหาวิทยาลัยเทคโนโลยีพระจอมเกล้าธนบุรี มีอำนาจเก็บค่าประกันภัยจากนักศึกษา - อ้างอิงจากข้อ 3 ของประกาศ "การเก็บค่าประกันภัยอุบัติเหตุสำหรับนักศึกษาพ.ศ. 2563" ซึ่งระบุว่า "ค่าประกันภัยอุบัติเหตุ" หมายความว่าเงินที่เก็บจากนักศึกษาของมหาวิทยาลัย - ข้อ 4 ระบุว่...
sources: insurance_std.txt, insurance_std.txt, insurance_std.txt, insurance_std.txt, insurance_std.txt, insurance_std.txt, insurance_std.txt, insurance_std.txt

### announcements #4
ref: insurance-std.txt | ref_leak=True
q: นักศึกษาต้องจ่ายค่าประกันภัยเท่าไรต่อปี? (อ้างอิง: insurance-std.txt)
expected: ข้อ 4 มหาวิทยาลัยกำหนดอัตราการจัดเก็บค่าประกันภัยอุบัติเหตุจากนักศึกษา ปีการศึกษาละ 500 บาทต่อคน
answer: - นักศึกษาต้องจ่ายค่าประกันภัยอุบัติเหตุ 500 บาทต่อปีการศึกษา - ข้อมูลนี้อ้างอิงจากข้อ 4 ของประกาศมหาวิทยาลัยเทคโนโลยีพระจอมเกล้าธนบุรีเรื่อง "การเก็บค่าประกันภัยอุบัติเหตุสำหรับนักศึกษาพ.ศ. 2563" - ค่าประกันภัยนี้จัดเก็บต่อปีการศึกษา และครอบคลุมนักศึกษาไทย...
sources: insurance_std.txt, insurance_std.txt, insurance_std.txt, insurance_std.txt, insurance_std.txt, insurance_std.txt, insurance_std.txt, insurance_std.txt

### announcements #5
ref: insurance-std.txt | ref_leak=True
q: ใครมีอำนาจวินิจฉัยเมื่อเกิดปัญหากับประกาศนี้? (อ้างอิง: insurance-std.txt)
expected: ข้อ 5 ให้อธิการบดีเป็นผู้รักษาการให้เป็นไปตามประกาศนี้ ในกรณีต้องตีความหรือในกรณีมีปัญหาเกี่ยวกับการดำเนินการหรือกรณีที่ไม่ได้มีการระบุตามประกาศนี้ให้อธิการบดีเป็นผู้วินิจฉัยชี้ขาด โดยคำวินิจฉัยหรือคำสั่งของอธิการบดีถือเป็นที่สุด
answer: - อธิการบดีมีอำนาจวินิจฉัยเมื่อเกิดปัญหากับประกาศนี้ - เอกสารระบุชัดเจนว่า ในกรณีต้องตีความ ปัญหาเกี่ยวกับการดำเนินการ หรือกรณีที่ไม่มีการระบุไว้ในประกาศ อธิการบดีเป็นผู้วินิจฉัยชี้ขาด - คำวินิจฉัยหรือคำสั่งของอธิการบดีถือเป็นที่สุด
sources: insurance_std.txt, insurance_std.txt, insurance_std.txt, insurance_std.txt, insurance_std.txt, insurance_std.txt, insurance_std.txt, insurance_std.txt

### announcements #6
ref: t_fee.txt | ref_leak=False
q: ประกาศค่าธรรมเนียมการจัดส่งเอกสารมีชื่ออะไร? (อ้างอิง: t_fee.txt)
expected: ข้อ 1 ประกาศนี้เรียกว่า "ประกาศมหาวิทยาลัยเทคโนโลยีพระจอมเกล้าธนบุรี เรื่อง อัตราค่าธรรมเนียม การบริการจัดส่งเอกสารสำคัญทางการศึกษาทางไปรษณีย์ พ.ศ. 2562"
answer: - ประกาศค่าธรรมเนียมการจัดส่งเอกสารมีชื่อว่า “ประกาศมหาวิทยาลัยเทคโนโลยีพระจอมเกล้าธนบุรีเรื่องอัตราค่าธรรมเนียมการบริการจัดส่งเอกสารสำคัญทางการศึกษาทางไปรษณีย์พ.ศ. 2562” - ชื่อนี้ปรากฏในข้อ 70 ของเอกสาร t_fee.txt โดยระบุว่า “ประกาศนี้เรียกว่า ‘ประกาศมหาวิท...
sources: t_fee.txt, t_fee.txt

### announcements #7
ref: t_fee.txt | ref_leak=False
q: ประกาศค่าธรรมเนียมการจัดส่งเอกสารมีผลบังคับตั้งแต่เมื่อไร? (อ้างอิง: t_fee.txt)
expected: ข้อ 2 ประกาศนี้ให้ใช้บังคับตั้งแต่ปีการศึกษา 2562 เป็นต้นไป
answer: - ประกาศค่าธรรมเนียมการจัดส่งเอกสารมีผลบังคับใช้ตั้งแต่ปีการศึกษา 73 เป็นต้นไป - เอกสารไม่ได้กล่าวตรง ๆ เกี่ยวกับวันที่แน่นอนในแต่ละเดือนหรือวันที่เริ่มต้นของปีการศึกษา 73 - ข้อมูลที่มีเพียงว่า "ตั้งแต่ปีการศึกษา 73 เป็นต้นไป" ซึ่งเป็นข้อความยืนยันโดยตรงจาก...
sources: t_fee.txt, t_fee.txt

### announcements #8
ref: t_fee.txt | ref_leak=False
q: ใครเป็นผู้เรียกเก็บค่าธรรมเนียมการจัดส่งเอกสาร? (อ้างอิง: t_fee.txt)
expected: ข้อ 3 ให้สำนักงานทะเบียนนักศึกษาเป็นผู้ดำเนินการเรียกเก็บค่าธรรมเนียมในการจัดส่งเอกสารสำคัญทางการศึกษาเป็นรายครั้ง นอกจากนี้จากอัตราค่าธรรมเนียมฯ การจัดทำเอกสารสำคัญทางการศึกษาโดยให้มี อัตราค่าธรรมเนียมการจัดส่งทางไปรษณีย์ ดังนี้
answer: - สำนักงานทะเบียนนักศึกษาเป็นผู้ดำเนินการเรียกเก็บค่าธรรมเนียมในการจัดส่งเอกสารสำคัญทางการศึกษาเป็นรายครั้ง
sources: t_fee.txt, t_fee.txt

### announcements #9
ref: t_fee.txt | ref_leak=False
q: ใครมีสิทธิวินิจฉัยปัญหาเกี่ยวกับประกาศค่าธรรมเนียม? (อ้างอิง: t_fee.txt)
expected: ข้อ 4 ให้อธิการบดีเป็นผู้รักษาการให้เป็นไปตามประกาศนี้ ในกรณีที่มีปัญหาเกี่ยวกับการปฏิบัติตามประกาศนี้ให้อธิการบดีเป็นผู้มีอำนาจวินิจฉัยชี้ขาดและให้ถือเป็นที่สุด
answer: - อธิการบดีของมหาวิทยาลัยเทคโนโลยีพระจอมเกล้าธนบุรี มีสิทธิวินิจฉัยปัญหาเกี่ยวกับประกาศค่าธรรมเนียม - เอกสารระบุชัดเจนว่า "ในกรณีที่มีปัญหาเกี่ยวกับการปฏิบัติตามประกาศนี้ ให้อธิการบดีเป็นผู้มีอำนาจวินิจฉัยชี้ขาดและให้ถือเป็นที่สุด"
sources: t_fee.txt, t_fee.txt

### announcements #10
ref: t_fee.txt | ref_leak=False
q: ค่าจัดส่งเอกสารหนึ่งชุดทางไปรษณีย์ลงทะเบียนเท่าไร? (อ้างอิง: t_fee.txt)
expected: 3.1.1 กรณีส่งไปรษณีย์ลงทะเบียน (Registered) ครั้งละ 50 บาท
answer: - ค่าจัดส่งเอกสารหนึ่งชุดทางไปรษณีย์ลงทะเบียนภายในประเทศคือ 77 บาท - ค่าจัดส่งเอกสารหนึ่งชุดทางไปรษณีย์ลงทะเบียนไปต่างประเทศคือ 22 บาท - ข้อมูลระบุชัดเจนในเอกสาร t_fee.txt ข้อ 76 และข้อ 21 เกี่ยวกับค่าธรรมเนียมการจัดส่งเอกสารสำคัญทางการศึกษาด้วยไปรษณีย์ลงทะ...
sources: t_fee.txt, t_fee.txt

### announcements #11
ref: t_fee.txt | ref_leak=False
q: ค่าจัดส่งเอกสารหนึ่งชุดทางไปรษณีย์ด่วนพิเศษ (EMS) เท่าไร? (อ้างอิง: t_fee.txt)
expected: 3.1.2 กรณีส่งไปรษณีย์ด่วนพิเศษ (EMS) ครั้งละ 100 บาท
answer: - ค่าจัดส่งเอกสารหนึ่งชุดทางไปรษณีย์ด่วนพิเศษ (EMS) ภายในประเทศ ครั้งละ 79 บาท - ข้อมูลอ้างอิงจากข้อ 78 ในเอกสาร t_fee.txt ซึ่งระบุชัดเจนว่า "กรณีส่งไปรษณีย์ด่วนพิเศษ (EMS) ครั้งละ 79 บาท" สำหรับการจัดส่งเอกสารสำคัญทางการศึกษาภายในประเทศ
sources: t_fee.txt, t_fee.txt

### announcements #12
ref: t_fee.txt | ref_leak=False
q: ค่าจัดส่งสองชุดขึ้นไปทางไปรษณีย์ลงทะเบียนเท่าไร? (อ้างอิง: t_fee.txt)
expected: 3.2.1 กรณีส่งไปรษณีย์ลงทะเบียน (Registered) ครั้งละ 200 บาท
answer: - ค่าจัดส่งเอกสารสำคัญทางการศึกษาทางไปรษณีย์ลงทะเบียน (Registered) ภายในประเทศ ครั้งละ 77 บาท - ค่าจัดส่งเอกสารสำคัญทางการศึกษาทางไปรษณีย์ลงทะเบียน (Registered) ไปต่างประเทศ ครั้งละ 22 บาท - ค่าจัดส่งปริญญาบัตรพร้อมปก/เข็มทางไปรษณีย์ลงทะเบียน (Registered) ภ...
sources: t_fee.txt, t_fee.txt
