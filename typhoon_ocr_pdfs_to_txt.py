from __future__ import annotations

import argparse
import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import requests
from pypdf import PdfReader


TYPHOON_OCR_URL = "https://api.opentyphoon.ai/v1/ocr"


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    return value


def load_dotenv_simple(root: Path, debug: bool = False) -> list[str]:
    """Minimal .env loader.

    Supports lines like:
      KEY=VALUE
      KEY = VALUE
    Ignores empty lines and comments starting with '#'.

    Does not override existing environment variables.
    """
    env_path = root / ".env"
    if not env_path.exists():
        return []
    try:
        raw_bytes = env_path.read_bytes()
        if debug:
            print(f"debug: .env bytes={len(raw_bytes)} prefix={raw_bytes[:4]!r}")
        if raw_bytes.startswith(b"\xff\xfe") or raw_bytes.startswith(b"\xfe\xff"):
            text = raw_bytes.decode("utf-16")
            decode_used = "utf-16"
        elif raw_bytes.startswith(b"\xef\xbb\xbf"):
            text = raw_bytes.decode("utf-8-sig")
            decode_used = "utf-8-sig"
        else:
            try:
                text = raw_bytes.decode("utf-8")
                decode_used = "utf-8"
            except UnicodeDecodeError:
                # Fallback for files saved by Windows tools.
                text = raw_bytes.decode("utf-16", errors="replace")
                decode_used = "utf-16(replace)"

        if debug:
            print(f"debug: .env decode={decode_used}")

        loaded_keys: list[str] = []
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip().lstrip("\ufeff")
            value = _strip_quotes(value.strip())
            if not key:
                continue
            if key in os.environ:
                continue
            os.environ[key] = value
            loaded_keys.append(key)

        if debug:
            # Print key names + value lengths only (never the secret values).
            print(f"debug: .env loaded keys={loaded_keys}")
            for k in loaded_keys:
                v = os.environ.get(k)
                print(f"debug: .env key {k} len={len(v) if v else 0}")

        return loaded_keys
    except Exception:
        if debug:
            import sys

            e = sys.exc_info()[1]
            print(f"debug: .env load error: {type(e).__name__}: {e}")
        # Fail silently in normal mode; user can still pass --api-key or set env var.
        return []


def iter_pdfs(root: Path) -> list[Path]:
    return sorted([p for p in root.rglob("*.pdf") if p.is_file()])


def safe_mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def unicode_alnum_ratio(text: str) -> float:
    if not text:
        return 0.0
    total = len(text)
    alnum = 0
    for ch in text:
        if ch.isalnum():
            alnum += 1
    return alnum / max(total, 1)


@dataclass(frozen=True)
class ExtractDecision:
    method: str  # "text-layer" | "ocr"
    reason: str
    text: str = ""


def extract_text_layer(pdf_path: Path, max_pages: Optional[int] = None) -> str:
    reader = PdfReader(str(pdf_path))
    pages = reader.pages
    if max_pages is not None:
        pages = pages[: max_pages]

    chunks: list[str] = []
    for page in pages:
        page_text = page.extract_text() or ""
        if page_text.strip():
            chunks.append(page_text)
    return "\n\n".join(chunks).strip()


def decide_extraction(pdf_path: Path, probe_pages: int = 3) -> ExtractDecision:
    try:
        probed = extract_text_layer(pdf_path, max_pages=probe_pages)
    except Exception as e:
        return ExtractDecision(method="ocr", reason=f"pypdf failed: {e}")

    if not probed:
        return ExtractDecision(method="ocr", reason="no text extracted from probe")

    # Heuristic: enough non-whitespace chars and reasonable alnum ratio.
    non_ws = sum(1 for c in probed if not c.isspace())
    ratio = unicode_alnum_ratio(probed)

    if non_ws >= 400 and ratio >= 0.10:
        # Likely real text-layer. Extract full text-layer.
        full = extract_text_layer(pdf_path, max_pages=None)
        if full:
            return ExtractDecision(method="text-layer", reason="sufficient text-layer found", text=full)

    return ExtractDecision(method="ocr", reason=f"insufficient text-layer (non_ws={non_ws}, alnum_ratio={ratio:.2f})")


def count_pages(pdf_path: Path) -> int:
    reader = PdfReader(str(pdf_path))
    return len(reader.pages)


def typhoon_ocr_pdf(
    pdf_path: Path,
    api_key: str,
    model: str = "typhoon-ocr",
    task_type: str = "default",
    max_tokens: int = 16384,
    temperature: float = 0.1,
    top_p: float = 0.6,
    repetition_penalty: float = 1.2,
    pages: Optional[list[int]] = None,
    timeout_s: int = 300,
    max_retries: int = 5,
) -> str:
    headers = {"Authorization": f"Bearer {api_key}"}

    data = {
        "model": model,
        "task_type": task_type,
        "max_tokens": str(max_tokens),
        "temperature": str(temperature),
        "top_p": str(top_p),
        "repetition_penalty": str(repetition_penalty),
    }
    if pages:
        data["pages"] = json.dumps(pages)

    session = requests.Session()

    last_error: Optional[str] = None
    for attempt in range(1, max_retries + 1):
        try:
            with pdf_path.open("rb") as f:
                files = {"file": f}
                resp = session.post(
                    TYPHOON_OCR_URL,
                    files=files,
                    data=data,
                    headers=headers,
                    timeout=timeout_s,
                )

            if resp.status_code == 200:
                result = resp.json()
                extracted_texts: list[str] = []
                for page_result in result.get("results", []):
                    if page_result.get("success") and page_result.get("message"):
                        content = page_result["message"]["choices"][0]["message"]["content"]
                        try:
                            parsed = json.loads(content)
                            text = parsed.get("natural_text", content)
                        except json.JSONDecodeError:
                            text = content
                        if text and text.strip():
                            extracted_texts.append(text.strip())
                    elif not page_result.get("success"):
                        err = page_result.get("error", "Unknown error")
                        extracted_texts.append(f"[OCR ERROR] {err}")
                return "\n\n".join(extracted_texts).strip()

            if resp.status_code in (429, 500, 502, 503, 504):
                retry_after = resp.headers.get("Retry-After")
                sleep_s = float(retry_after) if retry_after and retry_after.isdigit() else min(2**attempt, 30)
                last_error = f"HTTP {resp.status_code}: retry in {sleep_s}s"
                time.sleep(sleep_s)
                continue

            last_error = f"HTTP {resp.status_code}: {resp.text[:5000]}"
            break
        except requests.RequestException as e:
            last_error = f"Request error: {e}"
            time.sleep(min(2**attempt, 30))

    raise RuntimeError(last_error or "Typhoon OCR failed")


def write_text(out_path: Path, text: str) -> None:
    safe_mkdir(out_path.parent)
    out_path.write_text(text, encoding="utf-8")


def rel_to(root: Path, path: Path) -> Path:
    return path.relative_to(root)


def output_path_for(pdf_path: Path, root: Path, out_dir: Path) -> Path:
    rel = rel_to(root, pdf_path)
    return out_dir / rel.with_suffix(".txt")


def parse_pages(pages_str: Optional[str]) -> Optional[list[int]]:
    if not pages_str:
        return None
    # Accept formats: "1,2,3" or "1-5,9".
    pages: list[int] = []
    for part in pages_str.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            start = int(a.strip())
            end = int(b.strip())
            if end < start:
                start, end = end, start
            pages.extend(range(start, end + 1))
        else:
            pages.append(int(part))
    # Unique, keep order
    seen: set[int] = set()
    uniq: list[int] = []
    for p in pages:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch convert PDFs to .txt (text-layer first, else Typhoon OCR).")
    parser.add_argument("--root", default=".", help="Root folder to scan for PDFs (default: current workspace).")
    parser.add_argument("--out-dir", default="ocr_txt", help="Output base directory (default: ocr_txt).")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing .txt outputs.")
    parser.add_argument("--dry-run", action="store_true", help="Only report what would happen; do not write files.")
    parser.add_argument("--probe-pages", type=int, default=3, help="Pages to probe for text-layer decision.")
    parser.add_argument("--force-ocr", action="store_true", help="Always use OCR even if text-layer exists.")
    parser.add_argument("--pages", default=None, help='OCR specific pages, e.g. "1-5,9" (optional).')
    parser.add_argument("--auto-pages", action="store_true", help="Send all pages list to OCR API (optional).")

    parser.add_argument("--api-key", default=None, help="Typhoon API key (or set env TYPHOON_API_KEY).")
    parser.add_argument(
        "--debug-env",
        action="store_true",
        help="Print key-detection diagnostics (never prints the secret value).",
    )
    parser.add_argument("--model", default="typhoon-ocr")
    parser.add_argument("--task-type", default="default")
    parser.add_argument("--max-tokens", type=int, default=16384)
    parser.add_argument("--temperature", type=float, default=0.1)
    parser.add_argument("--top-p", type=float, default=0.6)
    parser.add_argument("--repetition-penalty", type=float, default=1.2)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--retries", type=int, default=5)

    args = parser.parse_args()

    logging.getLogger("pypdf").setLevel(logging.ERROR)

    root = Path(args.root).resolve()
    out_dir = (root / args.out_dir).resolve() if not Path(args.out_dir).is_absolute() else Path(args.out_dir).resolve()

    # Load .env (if present) so users can keep keys local.
    load_dotenv_simple(root, debug=args.debug_env)

    pdfs = iter_pdfs(root)
    if not pdfs:
        print(f"No PDFs found under: {root}")
        return 0

    api_key = (
        args.api_key
        or os.environ.get("TYPHOON_API_KEY")
        or os.environ.get("api_key")
        or os.environ.get("API_KEY")
    )

    if args.debug_env:
        env_path = root / ".env"
        print(f"debug: root={root}")
        print(f"debug: .env exists={env_path.exists()}")
        for k in ("TYPHOON_API_KEY", "api_key", "API_KEY"):
            v = os.environ.get(k)
            print(f"debug: env[{k}] present={bool(v)} len={len(v) if v else 0}")
        print(f"debug: args.api_key present={bool(args.api_key)}")
        print(f"debug: selected api_key present={bool(api_key)} len={len(api_key) if api_key else 0}")

    fixed_pages = parse_pages(args.pages)

    stats = {"text-layer": 0, "ocr": 0, "skipped": 0, "errors": 0}
    for pdf_path in pdfs:
        out_path = output_path_for(pdf_path, root=root, out_dir=out_dir)
        if out_path.exists() and not args.overwrite:
            stats["skipped"] += 1
            print(f"SKIP  {pdf_path} -> {out_path} (exists)")
            continue

        try:
            decision = ExtractDecision(method="ocr", reason="forced")
            if not args.force_ocr:
                decision = decide_extraction(pdf_path, probe_pages=args.probe_pages)

            if decision.method == "text-layer":
                stats["text-layer"] += 1
                print(f"TEXT  {pdf_path} -> {out_path} ({decision.reason})")
                if not args.dry_run:
                    write_text(out_path, decision.text)
                continue

            stats["ocr"] += 1
            print(f"OCR   {pdf_path} -> {out_path} ({decision.reason})")
            if args.dry_run:
                continue
            if not api_key:
                raise RuntimeError(
                    "Missing API key. Provide --api-key, set env TYPHOON_API_KEY, or add api_key=... in .env"
                )

            ocr_pages: Optional[list[int]] = fixed_pages
            if ocr_pages is None and args.auto_pages:
                n = count_pages(pdf_path)
                ocr_pages = list(range(1, n + 1))

            text = typhoon_ocr_pdf(
                pdf_path,
                api_key=api_key,
                model=args.model,
                task_type=args.task_type,
                max_tokens=args.max_tokens,
                temperature=args.temperature,
                top_p=args.top_p,
                repetition_penalty=args.repetition_penalty,
                pages=ocr_pages,
                timeout_s=args.timeout,
                max_retries=args.retries,
            )
            write_text(out_path, text)
        except Exception as e:
            stats["errors"] += 1
            print(f"ERROR {pdf_path}: {e}")

    print(
        "Done. "
        + ", ".join([
            f"text-layer={stats['text-layer']}",
            f"ocr={stats['ocr']}",
            f"skipped={stats['skipped']}",
            f"errors={stats['errors']}",
        ])
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
