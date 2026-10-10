from ml_ui.board_meeting_protocol.utils.api import (
    build_job_payload,
    merge_options,
)


def test_empty_model_list_keeps_the_previous_one():
    cached = {
        "backends": [
            {"id": "cursor", "available": True, "models": ["composer", "grok"]}
        ]
    }
    fresh = {"backends": [{"id": "cursor", "available": True, "models": []}]}
    merged = merge_options(fresh, cached)
    assert merged["backends"][0]["models"] == ["composer", "grok"]


def test_payload_omits_empty_models():
    payload = build_job_payload(
        mode="writing",
        backend="openai",
        rows=[{"left": None, "middle": None, "right": None, "note": ""}],
        new_input={"filename": "notes.docx", "content_base64": "YQ=="},
        orchestrator_note="  ",
        row_model=None,
        orchestrator_model=None,
    )
    assert payload["orchestrator_note"] == ""
    assert payload["rows"] == []
    assert "row_model" not in payload
    assert payload["mode"] == "writing"


def test_review_feedback_is_text():
    payload = build_job_payload(
        mode="reviewing",
        backend="openai",
        rows=[
            {
                "left": {"filename": "draft.docx", "content_base64": "YQ=="},
                "middle": {"filename": "final.docx", "content_base64": "Yg=="},
                "feedback": "  Subject: notes\n",
                "note": "",
            }
        ],
        new_input={"filename": "new.docx", "content_base64": "Yw=="},
        orchestrator_note="",
        row_model=None,
        orchestrator_model=None,
    )
    assert payload["rows"][0]["feedback"] == "Subject: notes"
    assert "right" not in payload["rows"][0]
