from __future__ import annotations

import html
import re
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from diagnose import DiagnosisError, api_key_configured, diagnose
from supabase_store import (
    SupabaseError,
    find_record,
    insert_record,
    list_records,
    update_redo,
)
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
DB_TEXT_FIELDS = [
    "problem_text",
    "student_code",
    "practice_scenario",
    "practice_code",
    "practice_answer",
    "practice_correct_code",
    "correct_code",
    "explanation",
    "raw_response",
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
    try:
        rows = list_records()
        st.session_state["supabase_error"] = ""
    except SupabaseError as exc:
        st.session_state["supabase_error"] = str(exc)
        return pd.DataFrame(columns=ROW_FIELDS + DB_TEXT_FIELDS + ["数据库ID", "显示编号"])

    data = []
    for row in rows:
        view_row = {
            "数据库ID": str(row.get("id", "")),
            "日期": str(row.get("date_label") or ""),
            "章节": str(row.get("chapter") or ""),
            "代码片段": str(row.get("display_id") or ""),
            "显示编号": str(row.get("display_id") or ""),
            "报错信息": str(row.get("compiler_error") or ""),
            "我判的类别": str(row.get("my_category") or ""),
            "它判的类别": str(row.get("ai_category") or ""),
            "对不对": "",
            "知识点": str(row.get("knowledge") or ""),
            "重做结果": str(row.get("redo_status") or "未重做"),
            "来源": str(row.get("source") or ""),
        }
        for field in DB_TEXT_FIELDS:
            view_row[field] = str(row.get(field) or "")
        data.append(view_row)
    return pd.DataFrame(
        data,
        columns=ROW_FIELDS + DB_TEXT_FIELDS + ["数据库ID", "显示编号"],
    )


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
    if "显示编号" not in df.columns:
        display_ids = []
        for index, raw_id in zip(df.index, df["代码片段"]):
            code_id = str(raw_id).strip()
            looks_like_image = bool(code_id) and Path(code_id).suffix.lower() in {
                ".png",
                ".jpg",
                ".jpeg",
            }
            display_ids.append(code_id if looks_like_image else f"H{int(index) + 1:03d}")
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
    raw_response: str,
) -> None:
    insert_record(
        {
            "display_id": code_id,
            "date_label": date.today().strftime("%Y-%m-%d"),
            "chapter": chapter,
            "source": source,
            "compiler_error": compiler_error.strip() or "无",
            "my_category": my_category,
            "ai_category": result["错因类别"],
            "knowledge": result["知识点"],
            "redo_status": redo,
            "problem_text": problem.strip(),
            "student_code": clean_code(code),
            "practice_scenario": result["同类题情景"],
            "practice_code": clean_code(result["同类题代码"]),
            "practice_answer": result["同类题答案"],
            "practice_correct_code": clean_code(result["同类题正确代码"]),
            "correct_code": clean_code(result["正确代码"]),
            "explanation": result["逐行说明"],
            "raw_response": raw_response,
        }
    )


def mark_done(record_uuid: str) -> int:
    if not record_uuid:
        return 0
    return update_redo(record_uuid)


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

    def summary_card(column, label: str, value: str, emphasized: bool = False) -> None:
        label_text = html.escape(label)
        value_text = html.escape(value or "未识别")
        value_size = "1.02rem" if emphasized else "0.95rem"
        column.markdown(
            f"""
            <div style="
                border: 1px solid rgba(128,128,128,.28);
                border-radius: 10px;
                padding: 12px 14px;
                min-height: 82px;
                background: rgba(128,128,128,.04);
            ">
                <div style="font-size: .78rem; opacity: .72; margin-bottom: 6px;">
                    {label_text}
                </div>
                <div style="
                    font-size: {value_size};
                    line-height: 1.4;
                    font-weight: 600;
                    white-space: normal;
                    overflow-wrap: anywhere;
                ">
                    {value_text}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    summary_card(col1, "错因类别", result["错因类别"], emphasized=True)
    summary_card(col2, "知识点", result["知识点"])
    summary_card(col3, "格式校验", "通过" if valid else "未通过", emphasized=True)

    if valid:
        st.success("11 段格式校验通过。")
    else:
        st.error("这条回答不能入库。")
        for problem in problems:
            st.write("- " + problem)
    st.caption("格式校验通过 ≠ 代码质量通过；保存前还要用 C 编译器验证同类题和正确代码。")

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
    if not valid or normalize_category(category) not in CATS:
        st.info("只有普通错误且 11 段校验通过后才能保存。")
        return

    st.subheader("保存错题")
    knowledge = result.get("知识点", "")
    automatic_chapter = CHAPTER.get(knowledge[:3], "第3章")
    with st.form("save_diagnosis_record"):
        col1, col2, col3 = st.columns(3)
        code_id = col1.text_input("编号", placeholder="例如 R004")
        source = col2.selectbox(
            "来源",
            ["真实作业", "构造测试", "挑战测试"],
            index=1,
        )
        chapter = col3.text_input("章节", automatic_chapter)
        col4, col5 = st.columns(2)
        my_category = col4.text_input("我判的类别", "没判出")
        redo = col5.text_input("重做结果", "未重做")
        code = st.text_area("原始代码", key="code_input", height=220)
        problem = st.text_area(
            "题目要求与样例",
            key="problem_input",
            height=130,
            placeholder="可选；会与代码、诊断结果一起保存到 Supabase。",
        )
        confirmed = st.checkbox("确认保存这一条")
        quality_confirmed = st.checkbox(
            "我已用 C 编译器验证：同类题能复现预期问题，正确代码能编译运行"
        )
        submitted = st.form_submit_button("保存记录")

    if submitted:
        st.session_state["save_notice"] = ""
        if not quality_confirmed:
            st.error("请先用编译器验证同类题和正确代码，再勾选质量确认。")
        elif not confirmed:
            st.error("请先勾选“确认保存这一条”。")
        elif not code_id.strip():
            st.error("请填写记录编号。")
        else:
            try:
                if find_record(code_id.strip()):
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
                        raw_response=st.session_state.get("raw_text", ""),
                    )
                    st.session_state["save_notice"] = code_id.strip()
                    st.rerun()
            except SupabaseError as exc:
                st.error(str(exc))

    if st.session_state.get("save_notice"):
        saved_id = st.session_state["save_notice"]
        st.success(
            f"保存成功：{saved_id} 已写入 Supabase。"
            "关闭电脑或重启网页后，仍可在“错题库与复习”中查看这条记录。"
        )


st.set_page_config(layout="wide", page_title="C 语言错因诊断助手", page_icon="🩺")

st.title("🩺 C 语言错因诊断助手")
st.caption("把 AI 回答转换为经过格式校验、可存档、可复习的错题数据。")

st.session_state.setdefault("raw_text", "")
st.session_state.setdefault("api_call_count", 0)
st.session_state.setdefault("code_input", "")
st.session_state.setdefault("problem_input", "")
st.session_state.setdefault("save_notice", "")
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
    try:
        database_count = len(list_records())
        st.success(f"Supabase 已连接 · {database_count} 条记录")
    except SupabaseError as exc:
        st.error(f"Supabase 未连接：{exc}")
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
        st.session_state["save_notice"] = ""
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
            st.session_state["save_notice"] = ""
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
    if st.session_state.get("supabase_error"):
        st.error(st.session_state["supabase_error"])
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
        display_id = str(record.get("显示编号", "")).strip()
        record_uuid = str(record.get("数据库ID", "")).strip()
        student_code = str(record.get("student_code", "")).strip()
        problem_text = str(record.get("problem_text", "")).strip()
        practice_code = str(record.get("practice_code", "")).strip()
        practice_answer = str(record.get("practice_answer", "")).strip()
        practice_correct_code = str(record.get("practice_correct_code", "")).strip()
        correct_code = str(record.get("correct_code", "")).strip()
        explanation = str(record.get("explanation", "")).strip()

        with st.container(border=True):
            st.subheader(record_label(selected_index))
            st.caption(f"记录编号：{display_id}")
            if student_code:
                st.markdown("**原始代码**")
                st.code(student_code, language="c")
            else:
                st.info("这条历史记录没有保存原始代码文本。")
            if problem_text:
                with st.expander("题目要求与样例"):
                    st.write(problem_text)
            if practice_code:
                with st.expander("同类题"):
                    st.code(practice_code, language="c")
                with st.expander("同类题答案"):
                    st.write(practice_answer or "无")
                with st.expander("同类题正确代码"):
                    st.code(practice_correct_code or "无", language="c")
            if correct_code:
                with st.expander("正确代码"):
                    st.code(correct_code, language="c")
            if explanation:
                with st.expander("逐行说明"):
                    st.write(explanation)

            if st.button("标记为已重做"):
                try:
                    changed = mark_done(record_uuid)
                    if changed:
                        st.success("已在 Supabase 中标记为已重做。")
                        st.rerun()
                    else:
                        st.warning("没有找到可更新的记录。")
                except SupabaseError as exc:
                    st.error(str(exc))

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
