from __future__ import annotations

import csv
import os
import re
import shutil
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from diagnose import DiagnosisError, api_key_configured, diagnose
from validator import CATS, check
from validator import parse as parse_sections


HERE = Path(__file__).resolve().parent
CSV_PATH = HERE / "records_v3.csv"
CODES_DIR = HERE / "codes"
ROW_FIELDS = [
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
CHAPTER = {
    "K01": "第1章",
    "K02": "第3章",
    "K03": "第3章",
    "K04": "第3章",
    "K05": "第3章",
    "K06": "第4章",
    "K07": "第5章",
    "K08": "第6章",
    "K09": "第6章",
    "K10": "第7章",
    "K11": "第7章",
    "K12": "第8章",
    "K13": "第8章",
    "K14": "第9章",
    "K15": "第10章",
}
CATEGORY_ALIASES = {
    "逻辑错误（整数除法）": "整数除法与除零",
    "逻辑错误(整数除法)": "整数除法与除零",
    "数据下标越界": "数组下标越界",
    "输入输出格式问题": "输入输出格式",
}


def load_rows() -> pd.DataFrame:
    with CSV_PATH.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    if not rows:
        return pd.DataFrame(columns=ROW_FIELDS)

    header = [item.strip() for item in rows[0]]
    positions = {name: header.index(name) for name in ROW_FIELDS if name in header}
    data = []
    for raw in rows[1:]:
        row = {}
        for name in ROW_FIELDS:
            position = positions.get(name)
            row[name] = raw[position].strip() if position is not None and position < len(raw) else ""
        data.append(row)
    return pd.DataFrame(data, columns=ROW_FIELDS)


def normalize_category(value: object) -> str:
    value = str(value).strip()
    value = CATEGORY_ALIASES.get(value, value)
    for category in CATS:
        if value == category or value.startswith(category + "（") or value.startswith(category + "("):
            return category
    return value


def normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["它判的类别"] = df["它判的类别"].map(normalize_category)
    df["重做结果"] = (
        df["重做结果"]
        .fillna("未重做")
        .astype(str)
        .str.strip()
        .replace({"": "未重做", "None": "未重做", "nan": "未重做", "NaN": "未重做"})
    )
    display_ids = []
    for index, raw_id in zip(df.index, df["代码片段"]):
        code_id = str(raw_id).strip()
        has_code_file = bool(code_id) and (CODES_DIR / f"{code_id}.c").exists()
        looks_like_image = bool(code_id) and Path(code_id).suffix.lower() in {
            ".png",
            ".jpg",
            ".jpeg",
        }
        display_ids.append(code_id if has_code_file or looks_like_image else f"H{int(index) + 1:03d}")
    df["显示编号"] = display_ids
    return df


def clean_code(text: str) -> str:
    lines = str(text).splitlines()
    out = []
    started = False
    for line in lines:
        stripped = line.strip()
        if not started:
            if stripped.startswith("#"):
                started = True
                out.append(line)
            continue
        if re.match(r"^题\s*\d", stripped):
            continue
        out.append(line)
    return "\n".join(out).strip()


def parse_result(text: str) -> dict:
    sections = parse_sections(text)
    return {
        "原文核对": sections.get("原文核对", ""),
        "错因类别": sections.get("错因类别", ""),
        "判断依据": sections.get("判断依据", ""),
        "知识点": sections.get("知识点", ""),
        "复习方向": sections.get("复习方向", ""),
        "同类题情景": sections.get("同类题情景", ""),
        "同类题代码": sections.get("同类题代码", ""),
        "同类题答案": sections.get("同类题答案", ""),
        "同类题正确代码": sections.get("同类题正确代码", ""),
        "正确代码": sections.get("正确代码", ""),
        "逐行说明": sections.get("逐行说明", ""),
    }


def save_record(
    code_id: str,
    source: str,
    chapter: str,
    my_category: str,
    redo: str,
    code: str,
    compiler_error: str,
    problem: str,
    result: dict,
) -> None:
    CODES_DIR.mkdir(exist_ok=True)
    files = {
        f"{code_id}.c": clean_code(code),
        f"{code_id}_practice.c": clean_code(result["同类题代码"]),
        f"{code_id}_answer.txt": result["同类题答案"],
        f"{code_id}_practice_correct.c": clean_code(result["同类题正确代码"]),
        f"{code_id}_correct.c": clean_code(result["正确代码"]),
        f"{code_id}_explain.txt": result["逐行说明"],
    }
    if problem.strip():
        files[f"{code_id}_problem.txt"] = problem.strip()

    for filename, content in files.items():
        (CODES_DIR / filename).write_text(content, encoding="utf-8")

    exists = CSV_PATH.exists() and CSV_PATH.stat().st_size > 0
    with CSV_PATH.open("a", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ROW_FIELDS)
        if not exists:
            writer.writeheader()
        writer.writerow(
            {
                "日期": date.today().strftime("%Y-%m-%d"),
                "章节": chapter,
                "代码片段": code_id,
                "报错信息": compiler_error.strip() or "无",
                "我判的类别": my_category,
                "它判的类别": result["错因类别"],
                "对不对": "",
                "知识点": result["知识点"],
                "重做结果": redo,
                "来源": source,
            }
        )


def mark_done(record_id: str) -> int:
    if not record_id:
        return 0
    shutil.copy(CSV_PATH, str(CSV_PATH) + ".bak")
    with CSV_PATH.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    header = [item.strip() for item in rows[0]]
    code_index = header.index("代码片段")
    done_index = header.index("重做结果")
    changed = 0
    for row in rows[1:]:
        if len(row) > max(code_index, done_index) and row[code_index].strip() == record_id:
            row[done_index] = "√ 已重做"
            changed += 1
    with CSV_PATH.open("w", encoding="utf-8-sig", newline="") as handle:
        csv.writer(handle).writerows(rows)
    return changed


def mark_done_at_index(index: int) -> None:
    shutil.copy(CSV_PATH, str(CSV_PATH) + ".bak")
    with CSV_PATH.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    header = [item.strip() for item in rows[0]]
    done_index = header.index("重做结果")
    row_number = int(index) + 1
    if row_number >= len(rows):
        raise ValueError("记录位置超出 CSV 范围。")
    while len(rows[row_number]) <= done_index:
        rows[row_number].append("")
    rows[row_number][done_index] = "√ 已重做"
    with CSV_PATH.open("w", encoding="utf-8-sig", newline="") as handle:
        csv.writer(handle).writerows(rows)


def history_summary(df: pd.DataFrame) -> str:
    top3 = df.loc[df["它判的类别"].isin(CATS), "它判的类别"].value_counts().head(3)
    recent = df["知识点"].dropna().astype(str).tail(3).tolist()
    return (
        "这是我最近的错误统计："
        + "、".join(f"{name}（{count}次）" for name, count in top3.items())
        + "。最近练过的知识点："
        + "、".join(recent)
        + "。请结合这些诊断下面的代码。"
    )


def render_result(raw_text: str) -> tuple[dict | None, bool, list[str]]:
    if not raw_text.strip():
        return None, False, []
    result = parse_result(raw_text)
    valid, problems = check(raw_text)

    st.subheader("诊断结果")
    col1, col2, col3 = st.columns(3)
    col1.metric("错因类别", result["错因类别"] or "未识别")
    col2.metric("知识点", result["知识点"] or "未识别")
    col3.metric("格式校验", "通过" if valid else "未通过")

    if valid:
        st.success("11 段格式校验通过。")
    else:
        st.error("这条回答不能入库。")
        for problem in problems:
            st.write("- " + problem)

    with st.container(border=True):
        st.markdown("### 判断依据")
        st.write(result["判断依据"])
        st.markdown("### 复习方向")
        st.write(result["复习方向"])

    tabs = st.tabs(["同类题", "正确代码", "逐行说明"])
    with tabs[0]:
        st.markdown("**题目情景**")
        st.write(result["同类题情景"])
        st.markdown("**题目代码**")
        st.code(result["同类题代码"], language="c")
        with st.expander("同类题答案"):
            st.write(result["同类题答案"])
        with st.expander("同类题正确代码"):
            st.code(result["同类题正确代码"], language="c")
    with tabs[1]:
        st.code(result["正确代码"], language="c")
    with tabs[2]:
        st.write(result["逐行说明"])

    with st.expander("查看原始 11 段回答"):
        st.text_area("原始回答", value=raw_text, height=300, disabled=True)

    return result, valid, problems


def render_save_form(result: dict, valid: bool) -> None:
    category = result.get("错因类别", "")
    if not valid or category not in CATS:
        st.info("只有普通错误且 11 段校验通过后才能保存。")
        return

    st.subheader("保存错题")
    knowledge = result.get("知识点", "")
    automatic_chapter = CHAPTER.get(knowledge[:3], "第3章")
    with st.form("save_diagnosis_record"):
        col1, col2, col3 = st.columns(3)
        code_id = col1.text_input("编号", placeholder="例如 R004")
        source = col2.selectbox("来源", ["真实作业", "构造测试", "挑战测试"])
        chapter = col3.text_input("章节", automatic_chapter)
        col4, col5 = st.columns(2)
        my_category = col4.text_input("我判的类别", "没判出")
        redo = col5.text_input("重做结果", "未重做")
        code = st.text_area("原始代码", key="code_input", height=220)
        problem = st.text_area(
            "题目要求与样例",
            key="problem_input",
            height=130,
            placeholder="可选；会保存为单独的题目文件。",
        )
        confirmed = st.checkbox("确认保存这一条")
        submitted = st.form_submit_button("保存记录", disabled=not confirmed)

    if submitted:
        if not code_id.strip():
            st.error("请填写记录编号。")
        elif (CODES_DIR / f"{code_id.strip()}.c").exists():
            st.error("这个编号已经存在，请换一个编号。")
        else:
            save_record(
                code_id=code_id.strip(),
                source=source,
                chapter=chapter,
                my_category=my_category,
                redo=redo,
                code=code,
                compiler_error=st.session_state.get("diagnosis_error", ""),
                problem=problem,
                result=result,
            )
            st.success(f"已保存 {code_id.strip()}。")
            st.rerun()


st.set_page_config(layout="wide", page_title="C 语言错因诊断助手", page_icon="🩺")

st.title("🩺 C 语言错因诊断助手")
st.caption("把 AI 回答转换为经过格式校验、可存档、可复习的错题数据。")

st.session_state.setdefault("raw_text", "")
st.session_state.setdefault("api_call_count", 0)
st.session_state.setdefault("code_input", "")
st.session_state.setdefault("problem_input", "")
try:
    max_calls = max(0, int(st.secrets.get("MAX_API_CALLS_PER_SESSION", 100)))
except (TypeError, ValueError):
    max_calls = 100

with st.sidebar:
    st.subheader("运行状态")
    if api_key_configured():
        st.success("DeepSeek API 已连接")
    else:
        st.error("DeepSeek API 未配置")
    st.caption("诊断规则：v6 / 11 段 / 15 类错因 / K01–K15")
    st.warning("云端新增记录暂不保证永久保存，正式数据请先保存在本地。")
    if max_calls > 0:
        remaining = max(0, max_calls - st.session_state["api_call_count"])
        st.caption(f"本会话剩余诊断次数：{remaining}")

tab_diagnose, tab_records, tab_quality = st.tabs(["一键诊断", "错题库与复习", "项目质量"])

with tab_diagnose:
    with st.form("diagnosis_form"):
        left, right = st.columns(2)
        code_input = left.text_area(
            "出错的 C 代码",
            key="api_code",
            height=300,
            placeholder="#include <stdio.h>\n\nint main(void) {\n    ...\n}",
        )
        error_input = right.text_area(
            "编译器报错或运行现象",
            key="api_error",
            height=130,
            placeholder="例如：expected ';' before 'return'",
        )
        problem_input = right.text_area(
            "题目要求与样例（可留空）",
            key="api_problem",
            height=130,
            placeholder="代码能编译但结果取决于题意时填写；构造测试通常可以留空。",
        )
        submitted = st.form_submit_button("开始诊断", type="primary")

    if submitted:
        if not code_input.strip():
            st.error("请先输入出错的 C 代码。")
        elif max_calls > 0 and st.session_state["api_call_count"] >= max_calls:
            st.error("本次会话的诊断次数已经用完。")
        else:
            try:
                st.session_state["api_call_count"] += 1
                with st.spinner("DeepSeek 正在诊断，请稍候……"):
                    result_text = diagnose(code_input, error_input, problem_input)
                st.session_state["raw_text"] = result_text
                st.session_state["code_input"] = code_input
                st.session_state["diagnosis_error"] = error_input
                st.session_state["problem_input"] = problem_input
                st.rerun()
            except DiagnosisError as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(f"诊断过程出现意外错误：{exc}")

    with st.expander("高级：粘贴已有诊断回答"):
        manual_text = st.text_area("粘贴【】格式回答", key="manual_result", height=220)
        if st.button("载入并校验"):
            st.session_state["raw_text"] = manual_text
            st.session_state["code_input"] = code_input
            st.session_state["diagnosis_error"] = error_input
            st.session_state["problem_input"] = problem_input
            st.rerun()

    raw_text = st.session_state["raw_text"]
    parsed_result, is_valid, _ = render_result(raw_text)
    if parsed_result is not None:
        render_save_form(parsed_result, is_valid)

with tab_records:
    dataframe = normalize_dataframe(load_rows())
    st.subheader("当前档案")
    metric1, metric2, metric3, metric4 = st.columns(4)
    metric1.metric("记录总数", len(dataframe))
    metric2.metric("真实作业", int((dataframe["来源"] == "真实作业").sum()))
    metric3.metric("待重做", int((dataframe["重做结果"] == "未重做").sum()))
    metric4.metric(
        "覆盖错因",
        dataframe.loc[dataframe["它判的类别"].isin(CATS), "它判的类别"].nunique(),
    )

    st.subheader("今日复习")
    pending = dataframe[dataframe["重做结果"] == "未重做"].copy()
    frequencies = dataframe.loc[dataframe["它判的类别"].isin(CATS), "它判的类别"].value_counts()
    pending["优先级"] = pending["它判的类别"].map(frequencies).fillna(0)
    review = pending.sort_values("优先级", ascending=False).head(3)
    if review.empty:
        st.info("当前没有待重做题目。")
    else:
        st.dataframe(
            review[["显示编号", "它判的类别", "知识点"]],
            width="stretch",
            hide_index=True,
        )

    category = st.selectbox(
        "按类别筛选",
        ["全部"] + sorted(dataframe.loc[dataframe["它判的类别"].isin(CATS), "它判的类别"].unique()),
    )
    filtered = dataframe if category == "全部" else dataframe[dataframe["它判的类别"] == category]
    only_pending = st.checkbox("只看未重做")
    if only_pending:
        filtered = filtered[filtered["重做结果"] == "未重做"]

    st.dataframe(
        filtered[["显示编号", "日期", "它判的类别", "知识点", "重做结果", "来源"]],
        width="stretch",
        hide_index=True,
    )

    if filtered.empty:
        st.info("当前筛选条件下没有记录。")
    else:
        def record_label(index: int) -> str:
            row = filtered.loc[index]
            return f"{row.get('显示编号', '无编号')}｜{row.get('它判的类别', '')}"

        selected_index = st.selectbox("查看一条记录", filtered.index, format_func=record_label)
        record = filtered.loc[selected_index]
        record_id = str(record.get("代码片段", "")).strip()
        display_id = str(record.get("显示编号", "")).strip()
        code_path = CODES_DIR / f"{record_id}.c"
        problem_path = CODES_DIR / f"{record_id}_problem.txt"
        practice_path = CODES_DIR / f"{record_id}_practice.c"
        answer_path = CODES_DIR / f"{record_id}_answer.txt"
        practice_correct_path = CODES_DIR / f"{record_id}_practice_correct.c"
        correct_path = CODES_DIR / f"{record_id}_correct.c"
        explain_path = CODES_DIR / f"{record_id}_explain.txt"

        with st.container(border=True):
            st.subheader(record_label(selected_index))
            if record_id and record_id != display_id:
                st.caption(f"原始记录代号：{record_id}")
            if code_path.exists():
                st.markdown("**原始代码**")
                st.code(code_path.read_text(encoding="utf-8"), language="c")
            else:
                st.info("这条记录没有原始代码文件。")
            if problem_path.exists():
                with st.expander("题目要求与样例"):
                    st.write(problem_path.read_text(encoding="utf-8"))
            if practice_path.exists():
                with st.expander("同类题"):
                    st.code(practice_path.read_text(encoding="utf-8"), language="c")
                with st.expander("同类题答案"):
                    st.write(answer_path.read_text(encoding="utf-8") if answer_path.exists() else "无")
                with st.expander("同类题正确代码"):
                    st.code(
                        practice_correct_path.read_text(encoding="utf-8")
                        if practice_correct_path.exists()
                        else "无",
                        language="c",
                    )
            if correct_path.exists():
                with st.expander("正确代码"):
                    st.code(correct_path.read_text(encoding="utf-8"), language="c")
            if explain_path.exists():
                with st.expander("逐行说明"):
                    st.write(explain_path.read_text(encoding="utf-8"))

            if st.button("标记为已重做"):
                try:
                    mark_done_at_index(selected_index)
                    st.success("已标记为已重做。")
                    st.rerun()
                except ValueError as exc:
                    st.warning(str(exc))

with tab_quality:
    quality_data = normalize_dataframe(load_rows())
    st.subheader("错因分布")
    left_chart, right_chart = st.columns(2)
    with left_chart:
        st.markdown("**全部记录**")
        counts = quality_data["它判的类别"].value_counts().reindex(sorted(CATS), fill_value=0)
        st.bar_chart(counts)
    with right_chart:
        st.markdown("**真实作业**")
        real_counts = (
            quality_data[quality_data["来源"] == "真实作业"]["它判的类别"]
            .value_counts()
            .reindex(sorted(CATS), fill_value=0)
        )
        st.bar_chart(real_counts)

    st.subheader("自动质检")
    quality_left, quality_right = st.columns(2)
    compile_path = HERE / "compile_check.csv"
    runtime_path = HERE / "runtime_check.csv"
    with quality_left:
        if compile_path.exists():
            compile_data = pd.read_csv(compile_path, encoding="utf-8-sig")
            st.metric("编译检查文件", len(compile_data))
            st.metric("编译失败", int((compile_data["结果"] == "失败").sum()))
    with quality_right:
        if runtime_path.exists():
            runtime_data = pd.read_csv(runtime_path, encoding="utf-8-sig")
            st.metric("运行检查文件", len(runtime_data))
            st.metric(
                "运行崩溃/超时",
                int(runtime_data["运行"].astype(str).str.contains("崩溃|超时").sum()),
            )
    st.caption("抽检 8 条，合格 6 条（75%）；变式 5 道，4 道达到三级以上（80%）。")

    st.subheader("回答校验器")
    validation_text = st.text_area("粘贴一条完整回答", height=220)
    if st.button("单独校验"):
        validation_ok, validation_problems = check(validation_text)
        if validation_ok:
            st.success("校验通过。")
        else:
            st.error("校验未通过。")
            for problem in validation_problems:
                st.write("- " + problem)

    st.subheader("项目报告")
    report_lines = [
        "# C 语言错因诊断助手项目报告",
        "",
        f"- 记录总数：{len(quality_data)}",
        f"- 真实作业：{int((quality_data['来源'] == '真实作业').sum())}",
        f"- 待重做：{int((quality_data['重做结果'] == '未重做').sum())}",
        "- 固定输出：11 段结构化诊断",
        "- 规则：15 类错因与 K01–K15 知识点",
        "- 质控：格式校验、编译检查、运行检查",
    ]
    report_text = "\n".join(report_lines)
    st.download_button("下载 report.md", report_text, file_name="report.md")

    with st.expander("历史摘要（用于后续记忆实验）"):
        st.code(history_summary(quality_data), language="text")
