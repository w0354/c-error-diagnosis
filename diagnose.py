from __future__ import annotations

import json
import os
import re
import tomllib
import urllib.error
import urllib.request
from pathlib import Path


HERE = Path(__file__).resolve().parent
PROMPT_PATH = HERE / "prompt_v6.txt"
SECRETS_PATH = HERE / ".streamlit" / "secrets.toml"
PLACEHOLDER = "PASTE_YOUR_KEY_HERE"


class DiagnosisError(RuntimeError):
    """An error that is safe to show in the Streamlit interface."""


def _streamlit_secret(name: str) -> str:
    try:
        import streamlit as st

        value = st.secrets.get(name, "")
    except Exception:
        return ""
    return str(value) if value else ""


def load_settings() -> dict[str, str]:
    values = {
        "DEEPSEEK_API_KEY": os.environ.get("DEEPSEEK_API_KEY", ""),
        "DEEPSEEK_MODEL": os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"),
        "DEEPSEEK_BASE_URL": os.environ.get(
            "DEEPSEEK_BASE_URL", "https://api.deepseek.com"
        ),
    }

    configured_path = os.environ.get("DEEPSEEK_SECRETS_FILE")
    secrets_path = Path(configured_path) if configured_path else SECRETS_PATH
    if secrets_path.exists():
        try:
            with secrets_path.open("rb") as handle:
                file_values = tomllib.load(handle)
        except (OSError, tomllib.TOMLDecodeError) as exc:
            raise DiagnosisError("无法读取本地密钥文件，请检查 TOML 格式。") from exc
        for key in values:
            if not values[key] and file_values.get(key):
                values[key] = str(file_values[key])

    for key in values:
        if not values[key]:
            values[key] = _streamlit_secret(key)

    if not values["DEEPSEEK_API_KEY"] or values["DEEPSEEK_API_KEY"] == PLACEHOLDER:
        raise DiagnosisError("尚未配置 DeepSeek API Key。")

    return values


def api_key_configured() -> bool:
    try:
        load_settings()
        return True
    except DiagnosisError:
        return False


def _read_prompt() -> str:
    try:
        return PROMPT_PATH.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise DiagnosisError("无法读取 prompt_v6.txt。") from exc


def _build_messages(
    code: str,
    compiler_error: str,
    problem: str,
    history: str,
) -> list[dict[str, str]]:
    user_parts = [
        "请严格按系统提示中的固定 11 段格式诊断下面的代码。",
        "",
        "<<<学生代码开始>>>",
        code.strip(),
        "<<<学生代码结束>>>",
        "",
        "<<<编译器报错或运行现象开始>>>",
        compiler_error.strip() or "未提供编译器报错。",
        "<<<编译器报错或运行现象结束>>>",
    ]
    if problem.strip():
        user_parts.extend(
            [
                "",
                "<<<题目要求、样例与预期结果开始>>>",
                problem.strip(),
                "<<<题目要求、样例与预期结果结束>>>",
            ]
        )
    if history.strip():
        user_parts.extend(
            [
                "",
                "<<<历史摘要开始>>>",
                history.strip(),
                "<<<历史摘要结束>>>",
                "历史摘要只用于复习提示，不得覆盖本次代码和报错中的事实。",
            ]
        )

    return [
        {"role": "system", "content": _read_prompt()},
        {"role": "user", "content": "\n".join(user_parts)},
    ]


def _extract_content(payload: dict) -> str:
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise DiagnosisError("DeepSeek 返回了无法识别的结果格式。") from exc
    if not isinstance(content, str) or not content.strip():
        raise DiagnosisError("DeepSeek 没有返回诊断内容。")
    return content.strip()


def _normalize_original_section(content: str, code: str) -> str:
    expected = "\n".join(code.splitlines()[:3])
    pattern = re.compile(r"【原文核对】\s*.*?(?=\s*【错因类别】)", re.DOTALL)
    replacement = "【原文核对】\n" + expected + "\n\n"
    return pattern.sub(lambda _: replacement, content, count=1)


def diagnose(
    code: str,
    compiler_error: str,
    problem: str = "",
    history: str = "",
    timeout: int = 180,
) -> str:
    code = code.strip()
    compiler_error = compiler_error.strip()
    problem = problem.strip()
    history = history.strip()

    if not code:
        raise DiagnosisError("请先输入出错的 C 代码。")
    if len(code) > 16000:
        raise DiagnosisError("代码太长，请控制在 16000 个字符以内。")
    if len(compiler_error) > 6000:
        raise DiagnosisError("报错信息太长，请控制在 6000 个字符以内。")
    if len(problem) > 8000:
        raise DiagnosisError("题目要求和样例太长，请控制在 8000 个字符以内。")
    if len(history) > 4000:
        raise DiagnosisError("历史摘要太长，请控制在 4000 个字符以内。")

    settings = load_settings()
    endpoint = settings["DEEPSEEK_BASE_URL"].rstrip("/") + "/chat/completions"
    body = {
        "model": settings["DEEPSEEK_MODEL"],
        "messages": _build_messages(code, compiler_error, problem, history),
        "temperature": 0.1,
        "max_tokens": 3500,
        "stream": False,
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {settings['DEEPSEEK_API_KEY']}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")[:500]
        raise DiagnosisError(
            f"DeepSeek 请求失败（HTTP {exc.code}）。请检查 Key、余额和接口地址。"
            + (f" 返回信息：{details}" if details else "")
        ) from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise DiagnosisError("无法连接 DeepSeek，请检查网络后重试。") from exc

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise DiagnosisError("DeepSeek 返回内容不是有效 JSON。") from exc

    if payload.get("error"):
        message = payload["error"].get("message", "未知错误")
        raise DiagnosisError(f"DeepSeek 返回错误：{message}")

    content = _extract_content(payload)
    return _normalize_original_section(content, code)
