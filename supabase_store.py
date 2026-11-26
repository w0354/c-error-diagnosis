from __future__ import annotations

import json
import os
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
SECRETS_PATH = HERE / ".streamlit" / "secrets.toml"
OWNER_CODE = "owner"


class SupabaseError(RuntimeError):
    """An error that can safely be displayed by the application."""


def _streamlit_secret(name: str) -> str:
    try:
        import streamlit as st

        value = st.secrets.get(name, "")
    except Exception:
        return ""
    return str(value) if value else ""


def load_settings() -> tuple[str, str]:
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()

    configured_path = os.environ.get("SUPABASE_SECRETS_FILE")
    secrets_path = Path(configured_path) if configured_path else SECRETS_PATH
    if secrets_path.exists():
        try:
            with secrets_path.open("rb") as handle:
                values = tomllib.load(handle)
        except (OSError, tomllib.TOMLDecodeError) as exc:
            raise SupabaseError("无法读取 Supabase 本地配置。") from exc
        url = url or str(values.get("SUPABASE_URL", "")).strip()
        key = key or str(values.get("SUPABASE_SERVICE_ROLE_KEY", "")).strip()

    url = url or _streamlit_secret("SUPABASE_URL")
    key = key or _streamlit_secret("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise SupabaseError("尚未配置 SUPABASE_URL 或 SUPABASE_SERVICE_ROLE_KEY。")
    return url.rstrip("/"), key


def _request(
    method: str,
    path: str,
    *,
    params: dict[str, str] | None = None,
    payload: Any = None,
    prefer: str | None = None,
    timeout: int = 30,
) -> Any:
    base_url, key = load_settings()
    query = f"?{urllib.parse.urlencode(params)}" if params else ""
    request = urllib.request.Request(
        base_url + path + query,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None,
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            **({"Prefer": prefer} if prefer else {}),
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:600]
        raise SupabaseError(f"Supabase 请求失败（HTTP {exc.code}）：{detail}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise SupabaseError("无法连接 Supabase，请检查网络后重试。") from exc

    if not body:
        return None
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise SupabaseError("Supabase 返回了无法识别的数据。") from exc


def list_records() -> list[dict]:
    rows = _request(
        "GET",
        "/rest/v1/records",
        params={
            "select": "*",
            "owner_code": f"eq.{OWNER_CODE}",
            "order": "created_at.asc",
        },
    )
    return rows if isinstance(rows, list) else []


def find_record(display_id: str) -> dict | None:
    rows = _request(
        "GET",
        "/rest/v1/records",
        params={
            "select": "*",
            "owner_code": f"eq.{OWNER_CODE}",
            "display_id": f"eq.{display_id}",
            "limit": "1",
        },
    )
    return rows[0] if isinstance(rows, list) and rows else None


def insert_record(record: dict) -> dict:
    record = {**record, "owner_code": OWNER_CODE}
    rows = _request(
        "POST",
        "/rest/v1/records",
        payload=[record],
        prefer="return=representation",
    )
    if not isinstance(rows, list) or not rows:
        raise SupabaseError("Supabase 没有返回已保存的记录。")
    return rows[0]


def upsert_records(records: list[dict]) -> int:
    if not records:
        return 0
    payload = [{**record, "owner_code": OWNER_CODE} for record in records]
    _request(
        "POST",
        "/rest/v1/records",
        params={"on_conflict": "owner_code,display_id"},
        payload=payload,
        prefer="resolution=merge-duplicates,return=minimal",
        timeout=60,
    )
    return len(payload)


def update_redo(record_uuid: str, redo_status: str = "√ 已重做") -> int:
    rows = _request(
        "PATCH",
        "/rest/v1/records",
        params={"id": f"eq.{record_uuid}", "owner_code": f"eq.{OWNER_CODE}"},
        payload={
            "redo_status": redo_status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
        prefer="return=representation",
    )
    return len(rows) if isinstance(rows, list) else 0


def delete_record(record_uuid: str) -> int:
    rows = _request(
        "DELETE",
        "/rest/v1/records",
        params={"id": f"eq.{record_uuid}", "owner_code": f"eq.{OWNER_CODE}"},
        prefer="return=representation",
    )
    return len(rows) if isinstance(rows, list) else 0


def count_records() -> int:
    return len(list_records())
