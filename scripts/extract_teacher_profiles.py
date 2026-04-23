import argparse
import csv
import json
import re
from pathlib import Path


DEFAULT_INPUT = Path("data/raw/curriculum/teacher.txt")
DEFAULT_CSV = Path("out/teacher_profiles.csv")
DEFAULT_JSON = Path("out/teacher_profiles.json")
DEFAULT_MD = Path("out/teacher_profiles.md")
DEFAULT_COURSES_CSV = Path("out/teacher_profiles_by_course.csv")

NAME_RE = re.compile(
    r"^(?:รศ\.ดร\.|ศ\.ดร\.|ผศ\.ดร\.|ผศ\.|อ\.ดร\.|อ\.)\s*[ก-๙][^\d]{1,120}$"
)
COURSE_RE = re.compile(r"^\s*([A-Z]{3})\s*(\d{3})\s+(.+?)\s+(\d+)\s*หน่วยกิต\s*$")


def normalize_ws(text: str) -> str:
    return " ".join(text.split())


def is_noise_line(line: str) -> bool:
    s = line.strip()
    if not s:
        return True
    if s.isdigit():
        return True
    if "อนุมัติจากสภา มจธ." in s:
        return True
    if s.startswith("ภาคผนวก ง. ประวัติอาจารย์ประจำหลักสูตร"):
        return True
    return False


def looks_like_name(line: str) -> bool:
    s = normalize_ws(line.strip())
    if not s:
        return False
    return bool(NAME_RE.match(s))


def cleanup_section_lines(lines):
    out = []
    prev_blank = False
    for raw in lines:
        s = raw.rstrip()
        if not s:
            if not prev_blank:
                out.append("")
            prev_blank = True
            continue
        prev_blank = False
        out.append(s)
    # Trim leading/trailing empty lines
    while out and not out[0]:
        out.pop(0)
    while out and not out[-1]:
        out.pop()
    return "\n".join(out)


def parse_profiles(text: str):
    profiles = []
    current = None
    section = None

    for raw_line in text.splitlines():
        line = raw_line.rstrip("\n")
        stripped = line.strip()

        if looks_like_name(stripped):
            if current:
                current["education"] = cleanup_section_lines(current["education_lines"])
                current["teaching_load"] = cleanup_section_lines(current["teaching_lines"])
                current["publications_5y"] = cleanup_section_lines(current["publications_lines"])
                profiles.append(current)
            current = {
                "name": normalize_ws(stripped),
                "education_lines": [],
                "teaching_lines": [],
                "publications_lines": [],
            }
            section = None
            continue

        if current is None:
            continue

        if re.match(r"^\s*1\.\s*ประวัติการศึกษา", stripped):
            section = "education"
            continue

        if re.match(r"^\s*2\.\s*ภาระงานสอน", stripped):
            section = "teaching"
            continue

        if "ผลงานวิชาการย้อนหลัง 5 ปี" in stripped:
            section = "publications"
            continue

        if re.match(r"^\s*3\.\s*เหตุผลที่ได้รับมอบหมาย", stripped):
            # Keep waiting for "ผลงานวิชาการย้อนหลัง 5 ปี" heading.
            section = None
            continue

        if is_noise_line(stripped):
            continue

        if section == "education":
            current["education_lines"].append(line.strip())
        elif section == "teaching":
            current["teaching_lines"].append(line.strip())
        elif section == "publications":
            current["publications_lines"].append(line.strip())

    if current:
        current["education"] = cleanup_section_lines(current["education_lines"])
        current["teaching_load"] = cleanup_section_lines(current["teaching_lines"])
        current["publications_5y"] = cleanup_section_lines(current["publications_lines"])
        profiles.append(current)

    # Drop temporary fields.
    cleaned = []
    for p in profiles:
        cleaned.append(
            {
                "name": p["name"],
                "education": p.get("education", ""),
                "teaching_load": p.get("teaching_load", ""),
                "publications_5y": p.get("publications_5y", ""),
            }
        )
    return cleaned


def write_csv(rows, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["name", "education", "teaching_load", "publications_5y"],
        )
        writer.writeheader()
        writer.writerows(rows)


def write_json(rows, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)


def write_markdown(rows, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        f.write("| ชื่อ | ประวัติการศึกษา | ภาระงานสอน | ผลงานวิชาการย้อนหลัง 5 ปี |\n")
        f.write("|---|---|---|---|\n")
        for r in rows:
            edu = r["education"].replace("\n", "<br>")
            teach = r["teaching_load"].replace("\n", "<br>")
            pubs = r["publications_5y"].replace("\n", "<br>")
            name = r["name"].replace("|", "\\|")
            f.write(f"| {name} | {edu} | {teach} | {pubs} |\n")


def explode_courses(rows):
    out = []
    for r in rows:
        teacher = r["name"]
        lines = r.get("teaching_load", "").splitlines()
        part = ""
        level = ""

        for raw in lines:
            line = raw.strip()
            if not line:
                continue

            if line.startswith("2.1"):
                part = "ภาระงานสอนในปัจจุบัน"
                continue
            if line.startswith("2.2"):
                part = "ภาระงานสอนในหลักสูตรนี้"
                continue

            if "รายวิชาระดับปริญญาตรี" in line:
                level = "ปริญญาตรี"
                continue
            if "รายวิชาระดับปริญญาโท" in line:
                level = "ปริญญาโท"
                continue
            if "รายวิชาระดับปริญญาเอก" in line:
                level = "ปริญญาเอก"
                continue
            if "รายวิชาระดับบัณฑิตศึกษา" in line and not level:
                level = "บัณฑิตศึกษา"
                continue

            m = COURSE_RE.match(line)
            if not m:
                continue

            code = f"{m.group(1)} {m.group(2)}"
            title_th = normalize_ws(m.group(3))
            credits = int(m.group(4))
            out.append(
                {
                    "name": teacher,
                    "teaching_part": part,
                    "level": level,
                    "course_code": code,
                    "course_title_th": title_th,
                    "credits": credits,
                }
            )
    return out


def write_courses_csv(rows, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "name",
                "teaching_part",
                "level",
                "course_code",
                "course_title_th",
                "credits",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def build_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Extract teacher profiles from teacher.txt with fields: "
            "name, education, teaching load, publications in last 5 years"
        )
    )
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Input teacher txt path")
    parser.add_argument("--out-csv", default=str(DEFAULT_CSV), help="Output CSV path")
    parser.add_argument("--out-json", default=str(DEFAULT_JSON), help="Output JSON path")
    parser.add_argument("--out-md", default=str(DEFAULT_MD), help="Output Markdown path")
    parser.add_argument(
        "--out-courses-csv",
        default=str(DEFAULT_COURSES_CSV),
        help="Output one-row-per-course CSV path",
    )
    return parser


def main():
    args = build_parser().parse_args()
    input_path = Path(args.input)
    out_csv = Path(args.out_csv)
    out_json = Path(args.out_json)
    out_md = Path(args.out_md)
    out_courses_csv = Path(args.out_courses_csv)

    if not input_path.exists():
        raise SystemExit(f"Input not found: {input_path}")

    text = input_path.read_text(encoding="utf-8", errors="ignore")
    rows = parse_profiles(text)

    if not rows:
        raise SystemExit("No teacher profiles found. Check input format.")

    write_csv(rows, out_csv)
    write_json(rows, out_json)
    write_markdown(rows, out_md)
    course_rows = explode_courses(rows)
    write_courses_csv(course_rows, out_courses_csv)

    print(f"Profiles: {len(rows)}")
    print(f"CSV: {out_csv}")
    print(f"JSON: {out_json}")
    print(f"Markdown: {out_md}")
    print(f"Courses CSV: {out_courses_csv} ({len(course_rows)} rows)")


if __name__ == "__main__":
    main()
