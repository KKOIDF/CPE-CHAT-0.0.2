#!/usr/bin/env python3
import argparse
import json
import sys
import urllib.error
import urllib.request


def _post_json(url: str, payload: dict, timeout_s: int) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            body = resp.read().decode("utf-8", errors="replace")
        return json.loads(body)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else ""
        raise RuntimeError(f"HTTP {e.code} {e.reason}: {body}") from e


def main() -> int:
    ap = argparse.ArgumentParser(description="Smoke test /rag/query and print meta signals.")
    ap.add_argument("--base", default="http://localhost:8001", help="Base URL of rag-service")
    ap.add_argument("--timeout", type=int, default=60, help="HTTP timeout seconds")
    ap.add_argument("--domain", default="", help="Optional domain override (e.g., curriculum, regulations)")
    ap.add_argument(
        "--question",
        default="สรุปเงื่อนไขการสำเร็จการศึกษา และเกณฑ์การพ้นสภาพนักศึกษา ต้องอ้างอิงจากเอกสารอะไรบ้าง?",
        help="Question to query",
    )
    args = ap.parse_args()

    url = args.base.rstrip("/") + "/rag/query"
    payload = {"question": args.question}
    if (args.domain or "").strip():
        payload["domain"] = args.domain.strip()

    out = _post_json(url, payload, timeout_s=args.timeout)

    meta = out.get("meta") or {}
    ctx = out.get("contexts") or []

    # Minimal, stable output: keep it grep-friendly.
    print("ok=1")
    print(f"ctx_n={len(ctx)}")
    print(f"token_est={out.get('token_est', 0)}")

    if meta:
        print(f"multi_doc_mode={meta.get('multi_doc_mode')}")
        print(f"multi_doc_triggered={int(bool(meta.get('multi_doc_triggered')))}")
        print(f"multi_doc_used={int(bool(meta.get('multi_doc_used')))}")
        print(f"multi_doc_reason={meta.get('multi_doc_reason')}")
        print(f"retrieved_unique_sources={meta.get('retrieved_unique_sources')}")
        print(f"retrieved_unique_domains={meta.get('retrieved_unique_domains')}")
        subqs = meta.get("multi_doc_subqs")
        if isinstance(subqs, list) and subqs:
            print(f"multi_doc_subqs_n={len(subqs)}")
    else:
        print("meta_missing=1")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
