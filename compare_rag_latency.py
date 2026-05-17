import json
import time
import statistics
import urllib.request
import urllib.error

BASE_URL = "http://localhost:8001"
QUESTION = "เงื่อนไขการสำเร็จหลักสูตรมีอะไรบ้าง"
MODEL = "gemma4:26b"
N_RUNS = 3
TIMEOUT = 120


def post_json(url, payload):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            elapsed = time.perf_counter() - t0
            return {
                "ok": True,
                "status": resp.status,
                "elapsed": elapsed,
                "raw": raw,
                "json": json.loads(raw),
                "error": None,
            }
    except urllib.error.HTTPError as e:
        elapsed = time.perf_counter() - t0
        raw = e.read().decode("utf-8", errors="replace")
        return {
            "ok": False,
            "status": e.code,
            "elapsed": elapsed,
            "raw": raw,
            "json": None,
            "error": str(e),
        }
    except Exception as e:
        elapsed = time.perf_counter() - t0
        return {
            "ok": False,
            "status": None,
            "elapsed": elapsed,
            "raw": "",
            "json": None,
            "error": repr(e),
        }


def extract_rag_answer(payload):
    if not isinstance(payload, dict):
        return ""
    return str(payload.get("answer") or "")


def extract_openai_answer(payload):
    try:
        return str(payload["choices"][0]["message"]["content"] or "")
    except Exception:
        return ""


def summarize_times(times):
    if not times:
        return "no successful runs"

    return (
        f"min={min(times):.3f}s, "
        f"max={max(times):.3f}s, "
        f"avg={statistics.mean(times):.3f}s"
    )


def main():
    endpoints = [
        {
            "name": "/rag/answer",
            "url": f"{BASE_URL}/rag/answer",
            "payload": {
                "question": QUESTION,
                "domain": "auto",
            },
            "extract_answer": extract_rag_answer,
        },
        {
            "name": "/v1/chat/completions",
            "url": f"{BASE_URL}/v1/chat/completions",
            "payload": {
                "model": MODEL,
                "messages": [
                    {
                        "role": "user",
                        "content": QUESTION,
                    }
                ],
            },
            "extract_answer": extract_openai_answer,
        },
    ]

    print("=" * 80)
    print("RAG endpoint latency comparison")
    print(f"Question: {QUESTION}")
    print(f"Runs per endpoint: {N_RUNS}")
    print("=" * 80)

    all_results = {}

    for ep in endpoints:
        print(f"\n## Testing {ep['name']}")
        times = []
        answers = []

        for i in range(1, N_RUNS + 1):
            result = post_json(ep["url"], ep["payload"])
            answer = ep["extract_answer"](result["json"])
            answers.append(answer)

            if result["ok"]:
                times.append(result["elapsed"])

            print("-" * 80)
            print(f"Run {i}")
            print(f"Status: {result['status']}")
            print(f"Elapsed: {result['elapsed']:.3f}s")
            print(f"OK: {result['ok']}")

            if result["error"]:
                print(f"Error: {result['error']}")

            print("Answer preview:")
            print((answer or result["raw"])[:700].replace("\\n", "\n"))

        all_results[ep["name"]] = {
            "times": times,
            "answers": answers,
        }

        print("-" * 80)
        print(f"Summary for {ep['name']}: {summarize_times(times)}")

    print("\n" + "=" * 80)
    print("Final comparison")
    print("=" * 80)

    rag_times = all_results["/rag/answer"]["times"]
    v1_times = all_results["/v1/chat/completions"]["times"]

    print(f"/rag/answer timings:          {summarize_times(rag_times)}")
    print(f"/v1/chat/completions timings: {summarize_times(v1_times)}")

    if rag_times and v1_times:
        rag_avg = statistics.mean(rag_times)
        v1_avg = statistics.mean(v1_times)
        diff = v1_avg - rag_avg
        ratio = v1_avg / rag_avg if rag_avg else 0

        print(f"\nAverage difference: {diff:+.3f}s")
        print(f"Ratio v1/rag:       {ratio:.2f}x")

    rag_answer = all_results["/rag/answer"]["answers"][-1] if all_results["/rag/answer"]["answers"] else ""
    v1_answer = all_results["/v1/chat/completions"]["answers"][-1] if all_results["/v1/chat/completions"]["answers"] else ""

    print("\nAnswer equality check:")
    print(f"Exact same answer: {rag_answer.strip() == v1_answer.strip()}")

    print("\n/rag/answer final answer:")
    print(rag_answer)

    print("\n/v1/chat/completions final answer:")
    print(v1_answer)


if __name__ == "__main__":
    main()
