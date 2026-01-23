import { useState, useRef, useEffect } from "react";
import axios from "axios";

const DOMAIN_OPTIONS = [
  { value: "auto", label: "อัตโนมัติ" },
  { value: "announcements", label: "ประกาศ" },
  { value: "regulations", label: "ระเบียบ" },
  { value: "curriculum", label: "โครงสร้างรายวิชา" },
];

function inferDomain(question) {
  const q = (question || "").toLowerCase();
  // Heuristic routing for prototype: course codes => curriculum
  if (/\b(?:cpe|coe|cen|css|swe|it)\s*\d{3,4}\b/i.test(question || "")) return "curriculum";
  if (q.includes("โครงสร้าง") || q.includes("หลักสูตร") || q.includes("หน่วยกิต") || q.includes("รายวิชา")) {
    return "curriculum";
  }
  if (q.includes("ระเบียบ") || q.includes("ข้อบังคับ") || q.includes("ข้อกำหนด") || q.includes("นโยบาย")) {
    return "regulations";
  }
  if (q.includes("ประกาศ") || q.includes("แจ้ง") || q.includes("กำหนดการ") || q.includes("ปฏิทิน")) {
    return "announcements";
  }
  // Default to announcements for general department info
  return "announcements";
}

function citeLabelFromContext(ctx) {
  const src = ctx?.source || ctx?.path || "";
  const name = String(src).split(/[\\/]/).pop() || "unknown";
  const page = ctx?.page_start ?? 0;
  return `${name}/${page}`;
}

function App() {
  const [message, setMessage] = useState("");
  const [domain, setDomain] = useState("auto");
  const [history, setHistory] = useState([]);
  const [isSending, setIsSending] = useState(false);
  const chatContainerRef = useRef(null);

  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop =
        chatContainerRef.current.scrollHeight;
    }
  }, [history]);

  const sendMessage = async () => {
    const q = (message || "").trim();
    if (!q || isSending) return;

    const chosenDomain = domain === "auto" ? inferDomain(q) : domain;
    setIsSending(true);
    try {
      const res = await axios.post("/api/rag/answer", {
        question: q,
        domain: chosenDomain,
      });

      const data = res?.data || {};
      const contexts = Array.isArray(data.contexts) ? data.contexts : [];
      const sources = Array.from(
        new Set(contexts.map((c) => citeLabelFromContext(c)).filter(Boolean))
      );

      setHistory((prev) => [
        ...prev,
        {
          user: q,
          domain: chosenDomain,
          bot: data.answer || "",
          sources,
        },
      ]);
      setMessage("");
    } catch (e) {
      setHistory((prev) => [
        ...prev,
        {
          user: q,
          domain: chosenDomain,
          bot: "เกิดข้อผิดพลาดในการเชื่อมต่อบริการตอบคำถาม",
          sources: [],
        },
      ]);
    } finally {
      setIsSending(false);
    }
  };

  return (
    <div style={{ padding: "20px" }}>
      <h1>ChatCPE</h1>

      <div style={{ marginBottom: "10px", display: "flex", gap: "8px", alignItems: "center" }}>
        <label htmlFor="domain">หมวด:</label>
        <select
          id="domain"
          value={domain}
          onChange={(e) => setDomain(e.target.value)}
          style={{ padding: "6px" }}
        >
          {DOMAIN_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        <span style={{ color: "#666", fontSize: "12px" }}>
          เลือก “อัตโนมัติ” เพื่อให้ระบบเดาหมวดจากคำถาม
        </span>
      </div>

      {/* Chat input */}
      <div style={{ marginBottom: "10px" }}>
        <input
          type="text"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") sendMessage();
          }}
          placeholder="พิมพ์ข้อความ..."
          style={{ width: "60%", padding: "8px" }}
        />
        <button onClick={sendMessage} disabled={isSending} style={{ marginLeft: "8px" }}>
          {isSending ? "Sending..." : "Send"}
        </button>
      </div>

      {/* Chat history */}
      <div
        style={{
          border: "1px solid #ccc",
          padding: "10px",
          height: "360px",
          overflowY: "scroll",
          marginTop: "10px",
        }}
      >
        {history.map((h, i) => (
          <div key={i}>
            <p>
              <b>You:</b> {h.user}
            </p>
            <p>
              <b>Bot ({h.domain}):</b>
            </p>
            <pre style={{ whiteSpace: "pre-wrap", margin: 0 }}>{h.bot}</pre>
            {h.sources?.length ? (
              <div style={{ marginTop: "8px", fontSize: "12px", color: "#444" }}>
                <div><b>แหล่งอ้างอิง:</b></div>
                <ul style={{ marginTop: "4px" }}>
                  {h.sources.slice(0, 8).map((s) => (
                    <li key={s}>{s}</li>
                  ))}
                </ul>
              </div>
            ) : null}
            </p>
            <hr />
          </div>
        ))}
      </div>
    </div>
  );
}

export default App;
