from pathlib import Path
from typing import Tuple
import pandas as pd
import re


def extract_excel_text(path: str) -> Tuple[str, int]:
    file_path = Path(path)
    xl = pd.ExcelFile(file_path)
    parts = []
    sheet_count = 0
    for sheet in xl.sheet_names:
        try:
            df = xl.parse(sheet)
            # Convert to text by joining rows
            csv_text = df.to_csv(index=False)
            cleaned = _clean_text(csv_text)
            parts.append(f"[SHEET {sheet}]\n{cleaned}")
            sheet_count += 1
        except Exception:
            continue
    full_text = "\n\n".join(parts)
    return full_text, sheet_count


def _clean_text(text: str) -> str:
    text = re.sub(r"\r", "\n", text)
    text = re.sub(r"\n{2,}", "\n\n", text)
    return text.strip()

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python extract_excel.py <excel_path>")
    else:
        t, c = extract_excel_text(sys.argv[1])
        print(f"Sheets processed: {c}")
        print(t[:1000])
