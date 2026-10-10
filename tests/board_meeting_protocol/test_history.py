import stat

import pytest

from ml_ui.board_meeting_protocol.utils.history_store import (
    HistoryStoreError,
    has_history,
    history_path,
    load_history,
    save_history,
)


def _row() -> dict:
    return {
        "left": {"filename": "notes.docx", "content_base64": "YQ=="},
        "middle": {"filename": "done.pdf", "content_base64": "Yg=="},
        "feedback": "hello",
        "note": "context",
    }


def test_history_round_trip_overwrites_one_file(tmp_path, monkeypatch):
    monkeypatch.setenv("ML_HOMELAB_ROOT", str(tmp_path))
    save_history("writing", [_row()])
    path = history_path("writing")
    local = tmp_path / ".local" / "board_meeting_protocol"
    assert path == local / "writing.json"
    assert "ml_ui" not in path.parts
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(local.stat().st_mode) == 0o700
    assert load_history("writing") == [_row()]
    save_history("writing", [])
    assert load_history("writing") == []
    assert load_history("reviewing") is None
    assert has_history("writing")
    assert not has_history("reviewing")


def test_history_save_refuses_without_a_root(monkeypatch):
    monkeypatch.delenv("ML_HOMELAB_ROOT", raising=False)
    with pytest.raises(HistoryStoreError):
        save_history("writing", [])
