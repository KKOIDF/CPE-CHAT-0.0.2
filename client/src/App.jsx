import { useState, useRef, useEffect } from "react";
import axios from "axios";

function App() {
  const [message, setMessage] = useState("");
  const [reply, setReply] = useState("");
  const [history, setHistory] = useState([]);
  const chatContainerRef = useRef(null);
  const [file, setFile] = useState(null);

  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop =
        chatContainerRef.current.scrollHeight;
    }
  }, [history]);

  const sendMessage = async () => {
    if (!message) return;
    const res = await axios.post("http://localhost:5000/chat", { message });
    setReply(res.data.reply);
    setHistory([...history, { user: message, bot: res.data.reply }]);
    setMessage("");
  };

  const uploadFile = async () => {
    if (!file) return;
    const formData = new FormData();
    formData.append("file", file);

    const res = await axios.post("http://localhost:5000/upload-pdf", formData, {
      responseType: "blob",
      headers: { "Content-Type": "multipart/form-data" },
    });

    const url = window.URL.createObjectURL(new Blob([res.data]));
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", "response.pdf");
    document.body.appendChild(link);
    link.click();

    setFile(null);
    setHistory([
      ...history,
      { type: "file", user: file.name, bot: "📄 ไฟล์ PDF ส่งกลับเรียบร้อย" },
    ]);
  };

  return (
    <div style={{ padding: "20px" }}>
      <h1>ChatCPE</h1>

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
        />
        <button onClick={sendMessage}>Send</button>
      </div>

      {/* Upload PDF */}
      <div style={{ marginTop: "10px" }}>
        <input
          type="file"
          accept=".pdf"
          onChange={(e) => setFile(e.target.files[0])}
        />
        <button onClick={uploadFile}>Upload PDF</button>
      </div>

      {/* Chat history */}
      <div
        style={{
          border: "1px solid #ccc",
          padding: "10px",
          height: "200px",
          overflowY: "scroll",
          marginTop: "10px",
        }}
      >
        {history.map((h, i) => (
          <div key={i}>
            <p>
              <b>👤 You:</b> {h.type === "text" ? h.user : `📄 ${h.user}`}
            </p>
            <p>
              <b>🤖 Bot:</b> {h.bot}
            </p>
            <hr />
          </div>
        ))}
      </div>
    </div>
  );
}

export default App;
