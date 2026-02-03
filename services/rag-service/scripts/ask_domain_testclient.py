import argparse
import os
import sys
from pathlib import Path

# Ensure Windows console can print Thai
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
try:
    sys.stdout.reconfigure(encoding='utf-8')  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding='utf-8')  # type: ignore[attr-defined]
except Exception:
    pass

# Ensure local imports work when running from repo root
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from app.main import app


def main():
    p = argparse.ArgumentParser(description='Ask RAG /rag/answer with domain via FastAPI TestClient')
    p.add_argument('--domain', default='curriculum')
    p.add_argument('--question', default='โครงสร้างหลักสูตรวิศวกรรมคอมพิวเตอร์มีหน่วยกิตรวมกี่หน่วยกิต')
    p.add_argument('--show-contexts', type=int, default=5, help='how many context headers to print')
    args = p.parse_args()

    client = TestClient(app)
    payload = {
        'domain': args.domain,
        'question': args.question,
    }

    r = client.post('/rag/answer', json=payload)
    print('status:', r.status_code)
    data = r.json()

    ctx = data.get('contexts') or []
    print('domain:', args.domain)
    print('question:', args.question)
    print('contexts:', len(ctx))
    for i, c in enumerate(ctx[: max(0, int(args.show_contexts))], 1):
        print(f"  {i}. {c.get('path')}/{c.get('page_start')} score={c.get('score_rrf')}")

    print('\nanswer:')
    print(data.get('answer'))


if __name__ == '__main__':
    main()
