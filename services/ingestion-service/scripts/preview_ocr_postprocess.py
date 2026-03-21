import argparse
from pathlib import Path

from app.ocr_postprocess import postprocess_ocr_text


def main() -> int:
    ap = argparse.ArgumentParser(description="Preview OCR post-processing on a text file")
    ap.add_argument("--in", dest="in_path", required=True, help="Input .txt file containing OCR output")
    ap.add_argument("--out", dest="out_path", default="", help="Optional output file to write processed text")
    ap.add_argument("--merge-lines", action="store_true", help="Merge wrapped lines into paragraphs")
    ap.add_argument("--normalize-thai-digits", action="store_true", help="Convert Thai digits (๐-๙) to Arabic 0-9")
    ap.add_argument("--spell-correct-thai", action="store_true", help="Enable Thai spell correction (validate before using)")
    args = ap.parse_args()

    raw = Path(args.in_path).read_text(encoding="utf-8", errors="ignore")
    processed = postprocess_ocr_text(
        raw,
        merge_lines=args.merge_lines,
        normalize_thai_digits=args.normalize_thai_digits,
        spell_correct_thai=args.spell_correct_thai,
    )

    if args.out_path:
        Path(args.out_path).write_text(processed, encoding="utf-8")
    else:
        # Print a short preview to stdout
        print("=== BEFORE (first 80 lines) ===")
        print("\n".join(raw.splitlines()[:80]))
        print("\n=== AFTER (first 80 lines) ===")
        print("\n".join(processed.splitlines()[:80]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
