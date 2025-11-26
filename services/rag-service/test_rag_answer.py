import os, sys, time, json
import requests

def main():
    question = sys.argv[1] if len(sys.argv) > 1 else "รายวิชาบังคับสำคัญของหลักสูตรคืออะไร"
    url = os.getenv("RAG_URL", "http://127.0.0.1:8000/rag/answer")
    payload = {"question": question}
    t0 = time.time()
    try:
        resp = requests.post(url, json=payload, timeout=600)
    except Exception as e:
        print(f"Request failed: {e}")
        return
    dt = time.time() - t0
    print(f"Status: {resp.status_code} in {dt:.2f}s")
    if not resp.ok:
        print(resp.text)
        return
    data = resp.json()
    print("\nAnswer:\n" + data.get("answer", "(no answer)"))
    print("\nContexts:")
    for i, c in enumerate(data.get("contexts", []), 1):
        src = c.get("source") or c.get("path") or "?"
        p1 = c.get("page_start", c.get("page"))
        p2 = c.get("page_end", c.get("page"))
        print(f"[{i}] {src} p{p1}-{p2}")
    print("\nToken estimate:", data.get("token_est"))

if __name__ == "__main__":
    main()