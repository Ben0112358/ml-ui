import json
import os
from pathlib import Path

_MODES = {"writing", "reviewing"}


class HistoryStoreError(RuntimeError):
    pass


def history_path(mode: str, root: str | None = None) -> Path:
    if mode not in _MODES:
        raise HistoryStoreError("mode must be writing or reviewing")
    return _store_dir(root) / f"{mode}.json"


def save_history(mode: str, rows: list[dict], root: str | None = None) -> None:
    directory = _store_dir(root)
    path = history_path(mode, root)
    payload = {"rows": [_stored_row(row) for row in rows[:3]]}
    try:
        directory.mkdir(parents=True, mode=0o700, exist_ok=True)
        directory.chmod(0o700)
        _write_private(path, json.dumps(payload))
    except OSError as exc:
        raise HistoryStoreError(f"could not write {path.name}") from exc


def load_history(mode: str, root: str | None = None) -> list[dict] | None:
    path = history_path(mode, root)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise HistoryStoreError(f"could not read {path.name}") from exc
    rows = data.get("rows") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        return []
    return [_stored_row(row) for row in rows[:3] if isinstance(row, dict)]


def has_history(mode: str, root: str | None = None) -> bool:
    try:
        return history_path(mode, root).is_file()
    except HistoryStoreError:
        return False


def _store_dir(root: str | None) -> Path:
    base = root if root is not None else os.environ.get("ML_HOMELAB_ROOT", "")
    base = str(base).strip()
    if not base:
        raise HistoryStoreError("ML_HOMELAB_ROOT is not set")
    return Path(base) / ".local" / "board_meeting_protocol"


def _stored_row(row: dict) -> dict:
    return {
        "left": _part(row.get("left")),
        "middle": _part(row.get("middle")),
        "feedback": str(row.get("feedback") or "").strip(),
        "note": str(row.get("note") or "").strip(),
    }


def _part(value: object) -> dict | None:
    if not isinstance(value, dict):
        return None
    filename = str(value.get("filename") or "")
    content = str(value.get("content_base64") or "")
    if not filename or not content:
        return None
    return {"filename": filename, "content_base64": content}


def _write_private(path: Path, text: str) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    descriptor = os.open(path, flags, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(text)
    os.chmod(path, 0o600)
