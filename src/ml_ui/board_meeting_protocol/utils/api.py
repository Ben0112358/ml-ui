import base64
import os
from typing import Any

import requests


def serving_base_url() -> str:
    explicit = os.environ.get("SERVING_URL", "").strip()
    if explicit:
        return explicit.rstrip("/")
    if os.path.exists("/.dockerenv"):
        return "http://serving:8000"
    port = os.environ.get("SERVING_PORT", "8000").strip() or "8000"
    return f"http://127.0.0.1:{port}"


def merge_options(
    fresh: dict[str, Any], cached: dict[str, Any] | None
) -> dict[str, Any]:
    if not cached:
        return fresh
    previous = {item.get("id"): item for item in cached.get("backends") or []}
    for item in fresh.get("backends") or []:
        prior = previous.get(item.get("id")) or {}
        if (
            item.get("available")
            and not item.get("models")
            and prior.get("models")
        ):
            item["models"] = list(prior["models"])
    return fresh


def fetch_options(base_url: str | None = None) -> dict[str, Any]:
    url = (base_url or serving_base_url()).rstrip("/")
    response = requests.get(f"{url}/options", timeout=30)
    response.raise_for_status()
    return response.json()


def file_part(name: str, data: bytes) -> dict[str, str]:
    encoded = base64.b64encode(data).decode("ascii")
    return {"filename": name, "content_base64": encoded}


def build_job_payload(
    mode: str,
    backend: str,
    rows: list[dict[str, Any]],
    new_input: dict[str, str],
    orchestrator_note: str,
    row_model: str | None,
    orchestrator_model: str | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "mode": mode,
        "backend": backend,
        "rows": [item for item in (_clean_row(row) for row in rows) if item],
        "new_input": new_input,
        "orchestrator_note": orchestrator_note.strip(),
    }
    if row_model:
        payload["row_model"] = row_model
    if orchestrator_model:
        payload["orchestrator_model"] = orchestrator_model
    return payload


def _clean_row(row: dict[str, Any]) -> dict[str, Any] | None:
    item: dict[str, Any] = {}
    for key in ("left", "middle", "right"):
        if row.get(key):
            item[key] = row[key]
    note = str(row.get("note") or "").strip()
    if note:
        item["note"] = note
    feedback = str(row.get("feedback") or "").strip()
    if feedback:
        item["feedback"] = feedback
    if not item:
        return None
    return item


def start_job(payload: dict[str, Any], base_url: str | None = None) -> str:
    url = (base_url or serving_base_url()).rstrip("/")
    response = requests.post(f"{url}/jobs", json=payload, timeout=60)
    response.raise_for_status()
    return response.json()["job_id"]


def poll_job(job_id: str, base_url: str | None = None) -> dict[str, Any]:
    url = (base_url or serving_base_url()).rstrip("/")
    response = requests.get(f"{url}/jobs/{job_id}", timeout=30)
    response.raise_for_status()
    return response.json()
