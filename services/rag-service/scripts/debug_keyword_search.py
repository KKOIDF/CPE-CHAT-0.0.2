import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.sqlite_client import keyword_search, domain_sqlite_path

QUESTION = "โครงสร้างหลักสูตรวิศวกรรมคอมพิวเตอร์มีหน่วยกิตรวมกี่หน่วยกิต"
TARGET = "742e89c2698b761702288997fccf5bfd"  # page 5 chunk containing '130 หน่วยกิต'


def main():
    sqlite_path = domain_sqlite_path('curriculum')
    ids = keyword_search(QUESTION, limit=60, sqlite_path=sqlite_path)
    print('keyword_ids:', len(ids))
    print('has_target:', TARGET in ids)
    if TARGET in ids:
        print('target_rank:', ids.index(TARGET) + 1)
    print('first_20:', ids[:20])


if __name__ == '__main__':
    main()
