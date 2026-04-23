import argparse
import csv
import re
from pathlib import Path


DEFAULT_INPUT = Path("data/raw/curriculum/วศ.บ.-วศวกรรมคอมพวเตอร-ปรบปรง.64.txt")
DEFAULT_CSV = Path("out/instructor_to_courses.csv")
DEFAULT_MD = Path("out/instructor_to_courses.md")

APPENDIX_MARKER = "ภาคผนวก ง. ประวัติอาจารย์ประจำหลักสูตร"
TARGET_SECTION_MARKER = "2.2 ภาระงานสอนในหลักสูตรนี้"

INSTRUCTOR_NAME_RE = re.compile(
    r"^(?:รศ\.ดร\.|ศ\.ดร\.|ผศ\.ดร\.|ผศ\.|อ\.ดร\.|อ\.\s*ดร\.|อ\.)\s*.+$"
)
COURSE_RE = re.compile(r"^\s*([A-Z]{3})\s*(\d{3})\s+(.+?)\s+(\d+)\s*หน่วยกิต\s*$")


def normalize_space(text: str) -> str:
    return " ".join(text.split())


def is_instructor_name(line: str) -> bool:
    if not line:
        return False
    if any(ch.isdigit() for ch in line):
        return False
    return bool(INSTRUCTOR_NAME_RE.match(line))


def dedupe_courses(courses):
    seen = set()
    out = []
    for code, title, credits in courses:
        key = (code, title)
        if key in seen:
            continue
        seen.add(key)
        out.append((code, title, credits))
    return out


def extract_instructor_courses(text: str):
    instructor_to_courses = {}
    in_appendix = False
    in_target_section = False
    current_instructor = None

    for raw_line in text.splitlines():
        line = raw_line.strip()

        if not in_appendix:
            if APPENDIX_MARKER in line:
                in_appendix = True
            continue

        if is_instructor_name(line):
            current_instructor = normalize_space(line)
            instructor_to_courses.setdefault(current_instructor, [])
            in_target_section = False
            continue

        if current_instructor is None:
            continue

        if TARGET_SECTION_MARKER in line:
            in_target_section = True
            continue

        if in_target_section and line.startswith("3."):
            in_target_section = False
            continue

        if not in_target_section:
            continue

        match = COURSE_RE.match(line)
        if not match:
            continue

        code = f"{match.group(1)} {match.group(2)}"
        title = normalize_space(match.group(3))
        credits = int(match.group(4))
        instructor_to_courses[current_instructor].append((code, title, credits))

    # Remove empty instructors and dedupe duplicate rows.
    cleaned = {}
    for instructor, courses in instructor_to_courses.items():
        unique_courses = dedupe_courses(courses)
        if unique_courses:
            cleaned[instructor] = unique_courses
    return cleaned


def rows_from_mapping(mapping):
    rows = []
    for instructor in sorted(mapping.keys()):
        for code, title, credits in sorted(mapping[instructor], key=lambda x: x[0]):
            rows.append((instructor, code, title, credits))
    return rows


def write_csv(rows, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["instructor", "course_code", "course_title_th", "credits"])
        writer.writerows(rows)


def write_markdown(rows, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        f.write("| ผู้สอน | รหัสวิชา | รายวิชา | หน่วยกิต |\n")
        f.write("|---|---|---|---:|\n")
        for instructor, code, title, credits in rows:
            f.write(f"| {instructor} | {code} | {title} | {credits} |\n")


def build_arg_parser():
    parser = argparse.ArgumentParser(
        description="Extract instructor -> course table from curriculum raw text"
    )
    parser.add_argument(
        "--input",
        default=str(DEFAULT_INPUT),
        help="Path to raw curriculum txt",
    )
    parser.add_argument(
        "--out-csv",
        default=str(DEFAULT_CSV),
        help="Output CSV path",
    )
    parser.add_argument(
        "--out-md",
        default=str(DEFAULT_MD),
        help="Output Markdown table path",
    )
    return parser


def main():
    args = build_arg_parser().parse_args()

    input_path = Path(args.input)
    out_csv = Path(args.out_csv)
    out_md = Path(args.out_md)

    if not input_path.exists():
        raise SystemExit(f"Input not found: {input_path}")

    text = input_path.read_text(encoding="utf-8", errors="ignore")
    mapping = extract_instructor_courses(text)
    rows = rows_from_mapping(mapping)

    if not rows:
        raise SystemExit(
            "No instructor-course rows found. Check input file and text format markers."
        )

    write_csv(rows, out_csv)
    write_markdown(rows, out_md)

    print(f"Extracted instructors: {len(mapping)}")
    print(f"Extracted rows: {len(rows)}")
    print(f"CSV: {out_csv}")
    print(f"Markdown: {out_md}")


if __name__ == "__main__":
    main()
