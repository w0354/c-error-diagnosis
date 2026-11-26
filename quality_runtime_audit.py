from __future__ import annotations

import json
import subprocess
import tempfile
import time
from pathlib import Path

from quality_audit import TARGET_IDS, base_category, find_compiler
from supabase_store import list_records


HERE = Path(__file__).resolve().parent
CASES_PATH = HERE / "quality_cases.json"
OUTPUT_PATH = HERE / "runtime_audit.csv"
RUNTIME_CATEGORIES = {
    "逻辑错误",
    "输入输出格式",
    "数组下标越界",
    "循环边界",
    "变量未初始化",
    "整数除法与除零",
}


def compile_executable(compiler: str, source: str, workdir: Path, name: str, output_name: str) -> tuple[str, str]:
    source_path = workdir / f"{name}.c"
    exe_path = workdir / f"{output_name}.exe"
    source_path.write_text(source, encoding="utf-8")
    result = subprocess.run(
        [compiler, "-std=c99", "-O0", "-Wall", "-Wextra", str(source_path), "-o", str(exe_path)],
        capture_output=True,
        timeout=20,
    )
    stderr = result.stderr.decode("utf-8", errors="replace")
    if result.returncode != 0:
        return "失败", stderr
    return "通过", stderr


def run_executable(exe_path: Path, input_text: str) -> tuple[str, str]:
    try:
        result = subprocess.run(
            [str(exe_path)],
            input=input_text.encode("utf-8"),
            capture_output=True,
            timeout=5,
        )
    except subprocess.TimeoutExpired:
        return "超时", ""
    stdout = result.stdout.decode("utf-8", errors="replace")
    if result.returncode != 0:
        return f"异常退出({result.returncode})", stdout
    return "正常", stdout


def check_expected(stdout: str, expected: list[str]) -> bool:
    return all(token in stdout for token in expected)


def main() -> None:
    compiler = find_compiler()
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    db_rows = None
    last_error = None
    for attempt in range(4):
        try:
            db_rows = list_records()
            break
        except Exception as exc:
            last_error = exc
            if attempt < 3:
                time.sleep(3)
    if db_rows is None:
        raise RuntimeError(f"无法从 Supabase 读取记录：{last_error}") from last_error

    records = {
        str(row.get("display_id", "")).strip(): row
        for row in db_rows
        if str(row.get("display_id", "")).strip() in TARGET_IDS
    }
    output_rows = []
    summaries = []

    with tempfile.TemporaryDirectory(prefix="c-diagnosis-runtime-") as temp:
        workdir = Path(temp)
        for record_id in sorted(TARGET_IDS):
            record = records.get(record_id)
            if not record or record_id not in cases:
                continue
            spec = cases[record_id]
            result = {"记录": record_id, "类别": base_category(str(record.get("ai_category") or ""))}
            issues = []

            code = str(record.get("correct_code") or "")
            compile_status, compile_error = compile_executable(
                compiler, code, workdir, f"{record_id}_correct_src", f"{record_id}_correct"
            )
            result["原题正确代码编译"] = compile_status
            if compile_status != "通过":
                issues.append("原题正确代码编译失败")
            else:
                run_status, stdout = run_executable(
                    workdir / f"{record_id}_correct.exe", spec["correct"]["input"]
                )
                result["原题正确代码运行"] = run_status
                result["原题正确代码输出"] = stdout.strip()
                result["原题输出匹配"] = check_expected(stdout, spec["correct"]["expect_all"])
                if run_status != "正常" or not result["原题输出匹配"]:
                    issues.append("原题正确代码输出不符合测试预期")

            practice_code = str(record.get("practice_code") or "")
            practice_compile, practice_compile_error = compile_executable(
                compiler, practice_code, workdir, f"{record_id}_practice_src", f"{record_id}_practice"
            )
            result["同类题编译"] = practice_compile
            if base_category(result["类别"]) in RUNTIME_CATEGORIES and practice_compile != "通过":
                issues.append("逻辑/运行类同类题产生了额外编译错误")

            practice_correct = str(record.get("practice_correct_code") or "")
            pc_compile, pc_error = compile_executable(
                compiler, practice_correct, workdir, f"{record_id}_practice_correct_src", f"{record_id}_practice_correct"
            )
            result["同类题正确代码编译"] = pc_compile
            if pc_compile != "通过":
                issues.append("同类题正确代码编译失败")

            pc_stdout = ""
            pc_status = "未运行"
            if pc_compile == "通过":
                pc_status, pc_stdout = run_executable(
                    workdir / f"{record_id}_practice_correct.exe",
                    spec["practice_correct"]["input"],
                )
                result["同类题正确运行"] = pc_status
                result["同类题正确输出"] = pc_stdout.strip()
                result["同类题正确输出匹配"] = check_expected(
                    pc_stdout, spec["practice_correct"]["expect_all"]
                )
                if pc_status != "正常" or not result["同类题正确输出匹配"]:
                    issues.append("同类题正确代码输出不符合测试预期")

            if spec.get("practice_runtime") and practice_compile == "通过" and pc_compile == "通过":
                practice_status, practice_stdout = run_executable(
                    workdir / f"{record_id}_practice.exe", spec["practice_correct"]["input"]
                )
                result["同类题运行"] = practice_status
                result["同类题输出"] = practice_stdout.strip()
                if practice_status != "正常":
                    issues.append("同类题运行异常")
                if practice_stdout.strip() == pc_stdout.strip():
                    issues.append("同类题没有产生与正确代码不同的运行结果")
                    result["同类题错误复现"] = "否"
                else:
                    result["同类题错误复现"] = "是"

            result["问题"] = "；".join(issues)
            result["编译错误"] = (compile_error or practice_compile_error or pc_error)[:2000]
            output_rows.append(result)
            summaries.append({
                "记录": record_id,
                "问题数": len(issues),
                "问题": issues,
                "原题运行": result.get("原题正确代码运行"),
                "同类题编译": result.get("同类题编译"),
            })

    fieldnames = [
        "记录",
        "类别",
        "原题正确代码编译",
        "原题正确代码运行",
        "原题正确代码输出",
        "原题输出匹配",
        "同类题编译",
        "同类题正确代码编译",
        "同类题运行",
        "同类题正确运行",
        "同类题输出",
        "同类题正确输出",
        "同类题正确输出匹配",
        "同类题错误复现",
        "问题",
        "编译错误",
    ]
    import csv

    with OUTPUT_PATH.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    print(json.dumps({"compiler": compiler, "output": str(OUTPUT_PATH), "summary": summaries}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
