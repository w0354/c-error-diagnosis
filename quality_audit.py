from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from supabase_store import list_records


HERE = Path(__file__).resolve().parent
OUTPUT_CSV = HERE / "quality_audit.csv"
TARGET_IDS = {f"R{number:03d}" for number in range(4, 11)}
RUNTIME_CATEGORIES = {
    "逻辑错误",
    "输入输出格式",
    "数组下标越界",
    "循环边界",
    "变量未初始化",
    "整数除法与除零",
}
COMPILER_CANDIDATES = [
    r"D:\Program Files (x86)\Dev-Cpp\MinGW64\bin\gcc.exe",
    r"C:\Program Files (x86)\Dev-Cpp\MinGW64\bin\gcc.exe",
]


def find_compiler() -> str:
    configured = os.environ.get("C_COMPILER", "").strip()
    if configured and Path(configured).exists():
        return configured
    discovered = shutil.which("gcc") or shutil.which("gcc.exe")
    if discovered:
        return discovered
    for candidate in COMPILER_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    raise RuntimeError("未找到 gcc 编译器。")


def base_category(value: str) -> str:
    return str(value).split("（", 1)[0].split("(", 1)[0].strip()


def compile_source(compiler: str, source: str, workdir: Path, name: str) -> dict:
    if not source.strip():
        return {"status": "无代码", "warnings": "", "errors": ""}
    path = workdir / f"{name}.c"
    path.write_text(source, encoding="utf-8")
    try:
        result = subprocess.run(
            [
                compiler,
                "-fsyntax-only",
                "-std=c99",
                "-Wall",
                "-Wextra",
                str(path),
            ],
            capture_output=True,
            timeout=15,
        )
    except subprocess.TimeoutExpired:
        return {"status": "超时", "warnings": "", "errors": "编译超时"}

    stderr = result.stderr.decode("utf-8", errors="replace")
    warning_lines = [
        line for line in stderr.splitlines() if "warning:" in line.lower()
    ]
    error_lines = [
        line
        for line in stderr.splitlines()
        if "error:" in line.lower() or "fatal error:" in line.lower()
    ]
    if result.returncode != 0:
        status = "失败"
    elif warning_lines:
        status = "通过（有警告）"
    else:
        status = "通过"
    return {
        "status": status,
        "warnings": " | ".join(warning_lines)[:600],
        "errors": " | ".join(error_lines)[:1000],
    }


def main() -> None:
    compiler = find_compiler()
    records_from_db = None
    last_error = None
    for attempt in range(4):
        try:
            records_from_db = list_records()
            break
        except Exception as exc:
            last_error = exc
            if attempt < 3:
                time.sleep(3)
    if records_from_db is None:
        raise RuntimeError(f"无法从 Supabase 读取记录：{last_error}") from last_error

    records = [
        record
        for record in records_from_db
        if str(record.get("display_id", "")).strip() in TARGET_IDS
    ]
    records.sort(key=lambda item: item.get("display_id", ""))
    rows = []
    summaries = []

    with tempfile.TemporaryDirectory(prefix="c-diagnosis-audit-") as temp:
        workdir = Path(temp)
        for record in records:
            record_id = str(record.get("display_id") or "")
            category = base_category(str(record.get("ai_category") or ""))
            fields = {
                "student_code": compile_source(
                    compiler, str(record.get("student_code") or ""), workdir, f"{record_id}_student"
                ),
                "practice_code": compile_source(
                    compiler, str(record.get("practice_code") or ""), workdir, f"{record_id}_practice"
                ),
                "practice_correct_code": compile_source(
                    compiler, str(record.get("practice_correct_code") or ""), workdir, f"{record_id}_practice_correct"
                ),
                "correct_code": compile_source(
                    compiler, str(record.get("correct_code") or ""), workdir, f"{record_id}_correct"
                ),
            }

            issues = []
            for field in ("correct_code", "practice_correct_code"):
                if fields[field]["status"] not in {"通过", "通过（有警告）"}:
                    issues.append(f"{field}未通过编译")

            practice_text = str(record.get("practice_code") or "").strip()
            practice_correct_text = str(record.get("practice_correct_code") or "").strip()
            if practice_text and practice_text == practice_correct_text:
                issues.append("同类题代码与同类题正确代码相同，未制造错误")

            if category in RUNTIME_CATEGORIES and fields["practice_code"]["status"] == "失败":
                issues.append("同类题属于逻辑/运行类错误，却产生了额外编译错误")

            if fields["practice_code"]["warnings"]:
                issues.append("同类题编译有警告")

            summary = {
                "记录": record_id,
                "类别": category,
                "学生代码": fields["student_code"]["status"],
                "同类题": fields["practice_code"]["status"],
                "同类题期望": (
                    "应可编译且运行结果错误"
                    if category in RUNTIME_CATEGORIES
                    else "允许复现目标编译错误"
                ),
                "同类题正确代码": fields["practice_correct_code"]["status"],
                "原题正确代码": fields["correct_code"]["status"],
                "问题": "；".join(issues),
                "编译错误": " | ".join(
                    value["errors"] for value in fields.values() if value["errors"]
                )[:2000],
            }
            rows.append(summary)
            summaries.append(
                {
                    "记录": record_id,
                    "问题数": len(issues),
                    "问题": issues,
                    "同类题状态": fields["practice_code"]["status"],
                    "原题正确代码状态": fields["correct_code"]["status"],
                }
            )

    fieldnames = [
        "记录",
        "类别",
        "学生代码",
        "同类题",
        "同类题期望",
        "同类题正确代码",
        "原题正确代码",
        "问题",
        "编译错误",
    ]
    with OUTPUT_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(
        json.dumps(
            {
                "compiler": compiler,
                "records": len(rows),
                "output": str(OUTPUT_CSV),
                "summary": summaries,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
