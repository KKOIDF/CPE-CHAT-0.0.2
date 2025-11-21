import express from "express";
import cors from "cors";
import multer from "multer";
import PDFDocument from "pdfkit";
import fs from "fs";

const app = express();
const PORT = 5000;

app.use(cors());
app.use(express.json());

// ตั้งค่า multer สำหรับอัปโหลดไฟล์
const upload = multer({ dest: "uploads/" });

// Mock chatbot
function chatbotReply(message) {
  return `🤖 ตอบกลับจากบอท: "${message}"`;
}

// API chat ข้อความ
app.post("/chat", (req, res) => {
  const { message } = req.body;
  const reply = chatbotReply(message);
  res.json({ reply });
});

// API รับ PDF, ประมวลผล, ส่งกลับ
app.post("/upload-pdf", upload.single("file"), (req, res) => {
  const filePath = req.file.path;

  // ตัวอย่าง: อ่านไฟล์ PDF เดิมและใส่ข้อความสรุปกลับ
  const content = `สรุปหรือข้อความจากไฟล์: ${req.file.originalname}`;

  const doc = new PDFDocument();
  res.setHeader("Content-Type", "application/pdf");
  res.setHeader("Content-Disposition", "attachment; filename=response.pdf");

  doc.pipe(res);
  doc.text(content);
  doc.end();

  // ลบไฟล์ต้นฉบับหลังใช้งาน
  fs.unlink(filePath, (err) => {
    if (err) console.error(err);
  });
});

app.listen(PORT, () => console.log(`Server running at http://localhost:${PORT}`));
