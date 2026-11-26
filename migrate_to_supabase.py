from __future__ import annotations

import csv
import json
from pathlib import Path

from supabase_store import list_records, upsert_records


HERE = Path(__file__).resolve().parent
CSV_PATH = HERE / "records_v3.csv"
CODES_DIR = HERE / "codes"
FIELDS = [
    "日期",
    "章节",
    "代码片段",
    "报错信息",
    "我判的类别",
    "它判的类别",
    "对不对",
    "知识点",
    "重做结果",
    "来源",
]


def read_text(name: str) -> str:
    path = CODES_DIR / name
    return path.read_text(encoding="utf-8") if path.exists() else ""


def display_id_for(index: int, raw_id: str) -> str:
    raw_id = raw_id.strip()
    has_code = bool(raw_id) and (CODES_DIR / f"{raw_id}.c").exists()
    is_image = Path(raw_id).suffix.lower() in {".png", ".jpg", ".jpeg"}
    if has_code or is_image:
        return raw_id
    return f"H{index:03d}"


def main() -> None:
    with CSV_PATH.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        source_rows = list(reader)

    records = []
    for position, raw in enumerate(source_rows, start=1):
        raw_id = (raw.get("代码片段") or "").strip()
        display_id = display_id_for(position, raw_id)
        has_code = bool(raw_id) and (CODES_DIR / f"{raw_id}.c").exists()
        records.append(
            {
                "display_id": display_id,
                "date_label": (raw.get("日期") or "").strip(),
                "chapter": (raw.get("章节") or "").strip(),
                "source": (raw.get("来源") or "").strip(),
                "compiler_error": (raw.get("报错信息") or "").strip(),
                "my_category": (raw.get("我判的类别") or "").strip(),
                "ai_category": (raw.get("它判的类别") or "").strip(),
                "knowledge": (raw.get("知识点") or "").strip(),
                "redo_status": (raw.get("重做结果") or "未重做").strip() or "未重做",
                "student_code": read_text(f"{raw_id}.c") if has_code else "",
                "practice_code": read_text(f"{raw_id}_practice.c") if has_code else "",
                "practice_answer": read_text(f"{raw_id}_answer.txt") if has_code else "",
                "practice_correct_code": (
                    read_text(f"{raw_id}_practice_correct.c") if has_code else ""
                ),
                "correct_code": read_text(f"{raw_id}_correct.c") if has_code else "",
                "explanation": read_text(f"{raw_id}_explain.txt") if has_code else "",
                "problem_text": read_text(f"{raw_id}_problem.txt") if has_code else "",
            }
        )

    upsert_records(records)
    database_rows = list_records()
    print(
        json.dumps(
            {
                "local_records": len(records),
                "database_records": len(database_rows),
                "sample_ids": [row["display_id"] for row in database_rows[:5]],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
