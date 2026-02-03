from pathlib import Path
from typing import List
import pandas as pd

from .utils import clean_for_index


def _df_to_sheet_text(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return ''
    df = df.fillna('')
    df = df.astype(str)
    lines = [' | '.join(c.strip() for c in row if str(c).strip()) for row in df.values.tolist()]
    lines = [ln for ln in lines if ln.strip()]
    return '\n'.join(lines)


def extract_excel_to_records(xl_path: str) -> List[dict]:
    """Return list of records similar to page records for chunking."""
    p = Path(xl_path)
    records = []
    try:
        if p.suffix.lower() in ['.csv', '.tsv']:
            sep = '\t' if p.suffix.lower() == '.tsv' else ','
            try:
                df = pd.read_csv(p, sep=sep, encoding='utf-8-sig')
            except Exception:
                df = pd.read_csv(p, sep=sep, encoding='cp874', errors='ignore')
            sheets = {'CSV': df}
        else:
            sheets = pd.read_excel(p, sheet_name=None, engine=None)
    except Exception as e:
        print(f'WARN: failed to read table file {p.name}: {e}')
        sheets = {}

    for idx, (sheet_name, df) in enumerate(sheets.items(), start=1):
        raw = _df_to_sheet_text(df)
        clean = clean_for_index(raw)
        records.append({
            'source': str(p.resolve()),
            'page_no': idx,  # map sheet -> page_no
            'sheet': str(sheet_name),
            'method': 'excel',
            'text': clean,
            'paragraphs': [clean] if clean else [],
        })
    return records
