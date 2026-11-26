import json
import streamlit as st
import re
from validator import CATS, check
from diagnose import DiagnosisError, api_key_configured, diagnose
import csv
from datetime import date
import os
HERE = os.path.dirname(os.path.abspath(__file__))
import csv as csvmod

def mark_done_index(i):
    shutil.copy(CSV_PATH, CSV_PATH + ".bak")
    with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    header = [h.strip() for h in rows[0]]
    col = header.index("重做结果")
    line = i + 1
    while len(rows[line]) <= col:
        rows[line].append("")
    rows[line][col] = "√ 已重做"
    with open(CSV_PATH, "w", encoding="utf-8-sig", newline="") as f:
        csv.writer(f).writerows(rows)

def load_rows(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csvmod.reader(f))
    header = [h.strip() for h in rows[0]]
    data = []
    for r in rows[1:]:
        r = (r + [""] * len(header))[:len(header)]
        data.append(r)
    return pd.DataFrame(data, columns=header)

CSV_PATH = os.path.join(HERE, "records_v3.csv")
ROW_FIELDS = ["日期", "章节", "代码片段", "报错信息",
              "我判的类别", "它判的类别", "对不对",
              "知识点", "重做结果", "来源"]

def clean_code(text):
    lines = str(text).splitlines()
    out = []
    started = False
    for line in lines:
        s = line.strip()
        if not started:
            if s.startswith("#include"):
                started = True
                out.append(line)
            continue
        if re.match(r"^题\s*\d", s):
            continue
        out.append(line)
    return "\n".join(out).strip()

def save_row(row):
    exists = os.path.exists(CSV_PATH)
    with open(CSV_PATH, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=ROW_FIELDS)
        if not exists or os.path.getsize(CSV_PATH) == 0:
            writer.writeheader()
        writer.writerow(row)

import shutil

def mark_done(rec_id):
    shutil.copy(CSV_PATH, CSV_PATH + ".bak")
    with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    if not rows:
        return 0
    header = [h.strip() for h in rows[0]]
    if "代码片段" not in header or "重做结果" not in header:
        return 0
    i_code = header.index("代码片段")
    i_done = header.index("重做结果")
    count = 0
    for r in rows[1:]:
        if len(r) > max(i_code, i_done) and r[i_code].strip() == str(rec_id).strip():
            r[i_done] = "√ 已重做"
            count += 1
    with open(CSV_PATH, "w", encoding="utf-8-sig", newline="") as f:
        csv.writer(f).writerows(rows)
    return count

def parse(text):
    parts = re.split(r'【(.*?)】', text)
    d = {parts[i].strip(): parts[i + 1].strip() for i in range(1, len(parts), 2)}
    return {
        "原文核对": d.get("原文核对", ""),
        "错因类别": d.get("错因类别", ""),
        "判断依据": d.get("判断依据", ""),
        "知识点": d.get("知识点", ""),
        "复习方向": d.get("复习方向", ""),
        "同类题": {"代码": d.get("同类题代码", ""), "答案": d.get("同类题答案", "")},
        "同类题情景": d.get("同类题情景", ""),
        "同类题正确代码": d.get("同类题正确代码", ""),
        "正确代码": d.get("正确代码", ""),
        "逐行说明": d.get("逐行说明", ""),
    }

# 设置网页为宽屏显示模式
st.set_page_config(layout="wide", page_title="错因诊断渲染器")

st.title("🩺 AI 错因诊断工作台")

st.caption("输入代码和报错可直接诊断；生成结果仍必须通过 11 段校验后才能保存。")

st.session_state.setdefault("raw_text", "")
st.session_state.setdefault("api_call_count", 0)
MAX_API_CALLS_PER_SESSION = 10

with st.container(border=True):
    st.subheader("⚡ 一键诊断")
    if not api_key_configured():
        st.warning("当前环境尚未配置 DeepSeek API Key。仍可使用下方的粘贴校验模式。")

    with st.form("deepseek_diagnose_form"):
        api_code = st.text_area(
            "出错的 C 代码",
            key="api_code",
            height=260,
            placeholder="#include <stdio.h>\n\nint main(void) {\n    ...\n}",
        )
        api_error = st.text_area(
            "编译器报错或运行现象",
            key="api_error",
            height=110,
            placeholder="例如：expected '}' at end of input",
        )
        diagnose_clicked = st.form_submit_button("开始诊断", type="primary")

    if diagnose_clicked:
        if not api_code.strip():
            st.error("请先输入出错的 C 代码。")
        elif st.session_state["api_call_count"] >= MAX_API_CALLS_PER_SESSION:
            st.error("本次会话的诊断次数已用完，请刷新页面后继续，或稍后再试。")
        else:
            try:
                st.session_state["api_call_count"] += 1
                with st.spinner("DeepSeek 正在诊断，请稍候……"):
                    result = diagnose(api_code, api_error)
                st.session_state["raw_text"] = result
                st.session_state["diagnosis_source"] = "DeepSeek API"
                st.session_state["code_input"] = api_code
                st.session_state["diagnosis_error"] = api_error
                st.rerun()
            except DiagnosisError as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(f"诊断过程出现意外错误：{exc}")

if st.session_state.get("diagnosis_source"):
    st.info(f"最近一次结果来源：{st.session_state['diagnosis_source']}")

st.caption(
    f"费用保护：当前浏览器会话还可调用 "
    f"{max(0, MAX_API_CALLS_PER_SESSION - st.session_state['api_call_count'])} 次。"
)

# 将页面切成左右两栏
col_left, col_right = st.columns([1, 1], gap="large")

with col_left:
    st.subheader("📋粘贴诊断结果 ")

    # 使用你截图中的真实 JSON 作为默认示例
    default_json = ""

    raw_text = st.text_area(
        "粘贴或查看【】格式文本：",
        key="raw_text",
        height=400,
    )

with col_right:
    st.subheader("📖 诊断结果展示")
    if not raw_text.strip():
        st.session_state["last"] = None
        st.info("请在左侧在此粘贴【】格式文本。")
    else:
        st.session_state["last"] = None
        try:
            data = parse(raw_text)
            valid, problems = check(raw_text)
            st.session_state["last"] = data if valid else None

            if not valid:
                st.error("⚠️ 这条回答没有通过校验，不能入库：")
                for problem in problems:
                    st.write("- " + problem)
            else:
                st.success("✅ 11 段格式校验通过，可以保存")

            with st.container(border=True):
                # 1. 错因类别 (高亮显示)
                error_type = data.get("错因类别", "未知")
                st.markdown(f"#### 🚨 错因类别：<span style='color:red;'>{error_type}</span>", unsafe_allow_html=True)

                st.divider()  # 分割线

                # 2. 原文核对 (用代码块展示，自动识别换行)
                st.markdown("#### 💻 原文核对")
                st.code(data.get("原文核对", "无"), language="c")

                # 3. 判断依据
                st.markdown("#### 🔍 判断依据")
                st.write(data.get("判断依据", "无"))

                # 4. 知识点与复习方向
                col_k, col_r = st.columns(2)
                with col_k:
                    st.markdown(f"**💡 知识点：** `{data.get('知识点', '无')}`")
                with col_r:
                    st.markdown(f"**🎯 复习方向：**")
                    st.write(data.get("复习方向", "无"))

                st.divider()

                # 5. 同类题拓展
                st.markdown("#### 📌 同类题拓展")
                same_q = data.get("同类题", {})
                if same_q:
                    st.markdown("**题目情景：**")
                    st.write(data.get("同类题情景", "无"))
                    st.markdown("**题目代码：**")
                    st.code(same_q.get("代码", "无"), language="c")
                    with st.expander("重做题：看答案解析（先自己做）"):
                        st.write(same_q.get("答案", "无"))
                    with st.expander("重做题：正确代码"):
                        st.code(data.get("同类题正确代码", "暂无"), language="c")
                else:
                    st.info("无同类题数据。")

                st.markdown("---")
                with st.expander("原题：正确代码（先自己改，再看）"):
                    st.code(data.get("正确代码", "暂无"), language="c")
                with st.expander("原题：逐行说明"):
                    st.write(data.get("逐行说明", "暂无"))

        except Exception as e:
            st.error(
                "⚠️ 解析失败，请检查【】标记是否完整")

import pandas as pd

st.divider()
st.subheader("错因分布")
import os
HERE = os.path.dirname(os.path.abspath(__file__))
df = load_rows(CSV_PATH)
df.columns = df.columns.str.strip()
df["它判的类别"] = df["它判的类别"].astype(str).str.strip()

df["重做结果"] = (
    df["重做结果"].fillna("未重做").astype(str).str.strip()
    .replace({"": "未重做", "None": "未重做", "nan": "未重做", "NaN": "未重做"})
)

fix = {"逻辑错误（整数除法）": "整数除法与除零",
       "逻辑错误(整数除法)": "整数除法与除零",
       "数据下标越界": "数组下标越界",
       "输入输出格式问题": "输入输出格式"}
df["它判的类别"] = df["它判的类别"].replace(fix)

def normalize_category(value):
    value = str(value).strip()
    for category in CATS:
        if value == category or value.startswith(category + "（") or value.startswith(category + "("):
            return category
    return value

df["它判的类别"] = df["它判的类别"].map(normalize_category)

c1, c2, c3, c4 = st.columns(4)
c1.metric("记录总数", len(df))
c2.metric("真实作业", int((df["来源"] == "真实作业").sum()))
c3.metric("待重做", int((df["重做结果"] == "未重做").sum()))
c4.metric("覆盖错因", df.loc[df["它判的类别"].isin(CATS), "它判的类别"].nunique())

order = ["漏分号", "括号不配对", "预处理指令错误", "拼写错误",
         "变量未声明", "类型不匹配", "输入输出格式",
         "数组下标越界", "循环边界", "指针问题",
         "函数返回值与参数", "字符串处理", "变量未初始化",
         "逻辑错误", "整数除法与除零"]

counts = df["它判的类别"].value_counts().reindex(order, fill_value=0)
# 全部记录
counts_all = df["它判的类别"].value_counts().reindex(order, fill_value=0)

# 只看真实作业
real = df[df["来源"] == "真实作业"]
counts_real = real["它判的类别"].value_counts().reindex(order, fill_value=0)

left, right = st.columns(2)
with left:
    st.markdown("**全部记录**")
    st.bar_chart(counts_all)
with right:
    st.markdown("**真实作业**")
    st.bar_chart(counts_real)

st.subheader("带历史的提示")
top3 = df["它判的类别"].value_counts().head(3)
recent = df["知识点"].dropna().astype(str).tail(3).tolist()

history_prompt = (
    "这是我最近的错误统计：" +
    "、".join(f"{k}（{v}次）" for k, v in top3.items()) +
    "。最近练过的知识点：" + "、".join(recent) +
    "。请结合这些诊断下面的代码。\n\n我的代码：\n"
)
st.code(history_prompt, language="text")

st.divider()
st.subheader("回答校验")
txt = st.text_area("粘贴助手的完整回答", height=220, key="check_box")
if st.button("检查一下"):
    res = check(txt)
    if res is None:
        st.error("check() 没有返回值，请检查 validator.py")
    else:
        ok, problems = res
        if ok:
            st.success("合格")
        else:
            st.error("不合格")
            for p in problems:
                st.write("- " + p)

st.divider()
st.subheader("保存这条记录")
last = st.session_state.get("last")

CHAPTER = {
    "K01": "第1章", "K02": "第3章", "K03": "第3章", "K04": "第3章",
    "K05": "第3章", "K06": "第4章", "K07": "第5章", "K08": "第6章",
    "K09": "第6章", "K10": "第7章", "K11": "第7章", "K12": "第8章",
    "K13": "第8章", "K14": "第9章", "K15": "第10章",
}

if not last:
    st.info("先在左边粘贴一条回答")
else:
    kp = last.get("知识点", "")
    auto_chapter = CHAPTER.get(kp[:3], "第3章")

    c1, c2 = st.columns(2)
    with c1:
        source = st.selectbox("来源", ["真实作业", "构造测试", "挑战测试"])
        chapter = st.text_input("章节", auto_chapter)
    with c2:
        my_cat = st.text_input("我判的类别", "没判出")
        redo = st.text_input("重做结果", "未重做")

    code_text = st.text_area("原始代码", height=200, key="code_input")

    codes_dir = os.path.join(HERE, "codes")
    os.makedirs(codes_dir, exist_ok=True)

    code_id = st.text_input("编号", "")

    confirm = st.checkbox("确认保存这一条")
    if st.button("保存这一条", disabled=not confirm):
        if not code_id.strip():
            st.error("还没填编号，无法保存")
        else:
            with open(os.path.join(codes_dir, code_id.strip() + ".c"), "w", encoding="utf-8") as f:
                f.write(clean_code(code_text))
            with open(os.path.join(codes_dir, code_id.strip() + "_practice.c"), "w", encoding="utf-8") as f:
                f.write(clean_code(last.get("同类题", {}).get("代码", "")))
            with open(os.path.join(codes_dir, code_id.strip() + "_answer.txt"), "w", encoding="utf-8") as f:
                f.write(last.get("同类题", {}).get("答案", ""))
            with open(os.path.join(codes_dir, code_id.strip() + "_practice_correct.c"), "w", encoding="utf-8") as f:
                f.write(clean_code(last.get("同类题正确代码", "")))
            with open(os.path.join(codes_dir, code_id.strip() + "_correct.c"), "w", encoding="utf-8") as f:
                f.write(clean_code(last.get("正确代码", "")))
            with open(os.path.join(codes_dir, code_id.strip() + "_explain.txt"), "w", encoding="utf-8") as f:
                f.write(last.get("逐行说明", ""))

            row = {
                "日期": date.today().strftime("%Y-%m-%d"),
                "来源": source, "章节": chapter,
                "代码片段": code_id.strip(),
                "报错信息": st.session_state.get("diagnosis_error", "").strip() or "无",
                "我判的类别": my_cat,
                "它判的类别": last.get("错因类别", ""),
                "对不对": "", "知识点": kp,
                "重做结果": redo,
            }
            save_row(row)
            st.success("已保存")

st.divider()
st.subheader("错题列表")

df = load_rows(CSV_PATH)
df.columns = df.columns.str.strip()
df["重做结果"] = (
    df["重做结果"]
    .fillna("未重做")
    .astype(str)
    .str.strip()
    .replace({"": "未重做", "None": "未重做", "nan": "未重做", "NaN": "未重做"})
)

st.subheader("今日复习")

todo = df[df["重做结果"] == "未重做"].copy()
freq = df["它判的类别"].value_counts()

todo["优先级"] = todo["它判的类别"].map(freq).fillna(0)
today = todo.sort_values("优先级", ascending=False).head(3)

if today.empty:
    st.info("没有待重做的题，今天可以休息")
else:
    st.dataframe(today[["代码片段", "它判的类别", "知识点"]],
                 width="stretch")

cat = st.selectbox("按类别筛选", ["全部"] + sorted(df["它判的类别"].dropna().unique()))
view = df if cat == "全部" else df[df["它判的类别"] == cat]

only_todo = st.checkbox("只看未重做")
if only_todo:
    view = view[view["重做结果"] == "未重做"]

def rec_label(i):
    r = view.loc[i]
    v = r.get("代码片段", "")
    name = "" if pd.isna(v) else str(v).strip()
    if name:
        return f"{name}｜{r.get('它判的类别', '')}"
    return f"{i}｜{r.get('日期', '')}｜{r.get('它判的类别', '')}"

st.dataframe(
    view[["日期", "它判的类别", "知识点", "重做结果", "来源"]],
    width="stretch"
)


idx = st.selectbox(
    "选择一条错题",
    view.index,
    format_func=rec_label
)
row = view.loc[idx]
rec = str(row.get("代码片段", ""))

path = os.path.join(HERE, "codes", str(rec) + ".c")
if os.path.exists(path):
    st.code(open(path, encoding="utf-8").read(), language="c")
else:
    st.info("这条没有代码文件（早期记录）")

p_path = os.path.join(HERE, "codes", rec + "_practice.c")
a_path = os.path.join(HERE, "codes", rec + "_answer.txt")
pc_path = os.path.join(HERE, "codes", rec + "_practice_correct.c")
c_path = os.path.join(HERE, "codes", rec + "_correct.c")
e_path = os.path.join(HERE, "codes", rec + "_explain.txt")

if os.path.exists(p_path):
    st.markdown("**同类题（重做用）**")
    st.code(open(p_path, encoding="utf-8").read(), language="c")
    with st.expander("重做题：看答案解析（先自己做）"):
        st.write(open(a_path, encoding="utf-8").read() if os.path.exists(a_path) else "无答案")
    if os.path.exists(pc_path):
        with st.expander("重做题：正确代码"):
            st.code(open(pc_path, encoding="utf-8").read(), language="c")

if os.path.exists(c_path):
    with st.expander("原题：正确代码（先自己改，再看）"):
        st.code(open(c_path, encoding="utf-8").read(), language="c")

if os.path.exists(e_path):
    with st.expander("原题：逐行说明"):
        st.write(open(e_path, encoding="utf-8").read())

if st.button("标记为已重做"):
        mark_done_index(idx)
        st.success("已标记")
        st.rerun()

st.subheader("项目报告")
if st.button("生成报告"):
    total = len(df)
    real_n = int((df["来源"] == "真实作业").sum())
    todo_n = int(df["重做结果"].astype(str).str.strip().isin(["", "未重做", "nan"]).sum())
    top = df["它判的类别"].value_counts().head(3)

    lines = [
        "# 编程错因诊断智能体 项目报告",
        "",
        f"- 记录总数：{total}",
        f"- 真实作业：{real_n}",
        f"- 待重做：{todo_n}",
        "- 高频错因：" + "、".join(f"{k}（{v}次）" for k, v in top.items()),
        "- 系统能力：七段结构化输出、格式校验、错因统计、原题与同类题存档、复习队列、重做标记",
        "- 已知问题：结论固化、尖括号被吞、JSON 转义不稳、同类题片段不可编译",
    ]
    path = os.path.join(HERE, "report.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    st.success("已生成 report.md")
    st.markdown("\n".join(lines))

st.divider()
st.subheader("质量看板")

q1 = os.path.join(HERE, "compile_check.csv")
q2 = os.path.join(HERE, "runtime_check.csv")

if os.path.exists(q1):
    a = pd.read_csv(q1, encoding="utf-8-sig")
    c1, c2 = st.columns(2)
    c1.metric("编译检查文件", len(a))
    c2.metric("编译失败", int((a["结果"] == "失败").sum()))

if os.path.exists(q2):
    b = pd.read_csv(q2, encoding="utf-8-sig")
    c3, c4 = st.columns(2)
    c3.metric("运行检查文件", len(b))
    c4.metric("运行崩溃/超时", int(b["运行"].astype(str).str.contains("崩溃|超时").sum()))

st.caption("抽检 4 条，合格 3 条（75%）；变式 5 道，4 道达到三级以上（80%）。")
