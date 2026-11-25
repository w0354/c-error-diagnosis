import re

CATS = {"漏分号", "括号不配对", "预处理指令错误", "拼写错误",
        "变量未声明", "类型不匹配", "输入输出格式",
        "数组下标越界", "循环边界", "指针问题",
        "函数返回值与参数", "字符串处理", "变量未初始化",
        "逻辑错误", "整数除法与除零"}

FIELDS = ["原文核对", "错因类别", "判断依据", "知识点",
          "复习方向", "同类题代码", "同类题答案", "同类题情景",
          "同类题正确代码", "正确代码", "逐行说明"]

SPECIAL_CATS = {"无错误", "表外-待确认"}


def parse(text):
    parts = re.split(r'【(.*?)】', text)
    return {parts[i].strip(): parts[i + 1].strip()
            for i in range(1, len(parts), 2)}


def check(text):
    d = parse(text)
    problems = []
    for f in FIELDS:
        if not d.get(f):
            problems.append("缺少或为空：" + f)
    cat = d.get("错因类别", "").strip()
    if cat not in CATS and cat not in SPECIAL_CATS:
        problems.append("错因类别不在 15 类里")
    kp = d.get("知识点", "").strip()
    if cat not in SPECIAL_CATS and not re.fullmatch(
        r"K(?:0[1-9]|1[0-5])｜[^\n]+", kp
    ):
        problems.append("知识点不是 K01–K15")
    if cat not in SPECIAL_CATS and "main" not in d.get("同类题代码", ""):
        problems.append("同类题不是完整程序")
    if cat not in SPECIAL_CATS and "main" not in d.get("同类题正确代码", ""):
        problems.append("同类题正确代码不是完整程序")
    if cat not in SPECIAL_CATS and "main" not in d.get("正确代码", ""):
        problems.append("正确代码不是完整程序")
    if "```" in text:
        problems.append("回答中不能使用 Markdown 代码围栏")
    answer = d.get("同类题答案", "")
    if "#include" in answer or re.search(r"\bmain\s*\(", answer):
        problems.append("同类题答案不应粘贴完整代码")
    return not problems, problems
