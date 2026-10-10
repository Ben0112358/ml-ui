import base64
import time

import streamlit as st

from ml_ui.board_meeting_protocol.utils.api import (
    build_job_payload,
    fetch_options,
    file_part,
    merge_options,
    poll_job,
    start_job,
)
from ml_ui.utils import setup_logging

POLL_SECONDS = 0.5
LABELS = {
    "writing": (
        "Raw notes",
        "Finished protocol",
        "Review feedback (optional)",
        "New raw notes",
    ),
    "reviewing": (
        "First draft",
        "Final protocol",
        "Feedback email (optional)",
        "New draft",
    ),
}


def _upload(label: str, key: str) -> dict[str, str] | None:
    uploaded = st.file_uploader(
        label,
        type=["docx", "pdf", "odt"],
        key=key,
    )
    if uploaded is None:
        return None
    return file_part(uploaded.name, uploaded.getvalue())


def _load_options() -> dict | None:
    cached = st.session_state.get("options")
    try:
        fresh = fetch_options()
    except Exception as exc:
        if cached:
            return cached
        st.error(f"Could not reach the service: {exc}")
        return None
    merged = merge_options(fresh, cached)
    st.session_state.options = merged
    return merged


def _history_ids() -> list[int]:
    if "row_ids" not in st.session_state:
        st.session_state.row_ids = []
        st.session_state.next_row_id = 0
    return st.session_state.row_ids


def main() -> None:
    setup_logging()
    st.set_page_config(page_title="Board meeting protocol", layout="wide")
    st.title("Board meeting protocol")
    st.caption(
        "History rows are optional. Each row you add needs its first two "
        "documents; the third input is optional. "
        "Writing downloads a protocol in the same file type as the new notes, "
        "using the font and margins of the latest finished protocol when it "
        "can. Logos and tables are not copied. "
        "Reviewing returns feedback text you can copy. Nothing is sent. "
        "A HIGH UNCERTAINTY line names what is unclear. "
        "Fill that part in by hand or with an optional note."
    )
    options = _load_options()
    if options is None:
        _show_active_job()
        st.stop()

    mode = st.radio(
        "Mode",
        options["modes"],
        format_func=lambda item: item.capitalize(),
        horizontal=True,
    )
    left_label, middle_label, right_label, input_label = LABELS[mode]
    available = [item for item in options["backends"] if item.get("available")]
    if not available:
        st.warning(
            "No model backend is configured. Set OPENAI_BASE_URL, "
            "OPENAI_API_KEY, and OPENAI_MODEL, or CURSOR_API_KEY."
        )
        _show_active_job()
        st.stop()

    backend_id = st.selectbox(
        "Model backend",
        [item["id"] for item in available],
        format_func=lambda key: next(
            item["label"] for item in available if item["id"] == key
        ),
    )
    chosen = next(item for item in available if item["id"] == backend_id)
    row_model = None
    orchestrator_model = None
    if backend_id == "cursor":
        models = chosen.get("models") or []
        if not models:
            st.warning("Cursor is configured, but no model list was returned.")
            _show_active_job()
            st.stop()
        row_model = st.selectbox("Model for history rows", models)
        orchestrator_model = st.selectbox("Model for the orchestrator", models)

    max_rows = int(options.get("max_rows", 3))
    row_ids = _history_ids()
    if len(row_ids) < max_rows and st.button("Add history row"):
        row_ids.append(st.session_state.next_row_id)
        st.session_state.next_row_id += 1
    if not row_ids:
        st.info("No history rows. The run uses only the new document.")

    rows: list[dict] = []
    for number, row_id in enumerate(list(row_ids), start=1):
        st.subheader(f"History row {number}")
        if st.button("Remove this row", key=f"remove-{row_id}"):
            row_ids.remove(row_id)
            st.rerun()
        columns = st.columns(2)
        with columns[0]:
            left = _upload(left_label, f"{mode}-left-{row_id}")
        with columns[1]:
            middle = _upload(middle_label, f"{mode}-middle-{row_id}")
        feedback = st.text_area(
            right_label,
            key=f"{mode}-feedback-{row_id}",
            help="Paste the email. It is text, not a file.",
        )
        note = st.text_area(
            "Optional note for this row",
            key=f"{mode}-note-{row_id}",
        )
        rows.append(
            {
                "left": left,
                "middle": middle,
                "feedback": feedback.strip(),
                "note": note.strip(),
            }
        )

    st.subheader(input_label)
    new_file = st.file_uploader(
        "New document",
        type=["docx", "pdf", "odt"],
        key="new-input",
    )
    orchestrator_note = st.text_area(
        "Optional note for the orchestrator",
        help="Extra context beside the history and the new document.",
    )
    if st.button("Run", type="primary"):
        if new_file is None:
            st.error("Add the new document first.")
            st.stop()
        missing = [
            index
            for index, row in enumerate(rows, start=1)
            if row["left"] is None or row["middle"] is None
        ]
        if missing:
            labels = ", ".join(str(index) for index in missing)
            st.error(f"History row {labels} needs its first two documents.")
            st.stop()
        payload = build_job_payload(
            mode=mode,
            backend=backend_id,
            rows=rows,
            new_input=file_part(new_file.name, new_file.getvalue()),
            orchestrator_note=orchestrator_note,
            row_model=row_model,
            orchestrator_model=orchestrator_model,
        )
        try:
            st.session_state.active_job = start_job(payload)
        except Exception as exc:
            st.error(str(exc))
            st.stop()

    _show_active_job()


def _show_active_job() -> None:
    job_id = st.session_state.get("active_job")
    if not job_id:
        return
    try:
        job = poll_job(job_id)
    except Exception as exc:
        st.error(str(exc))
        return
    st.subheader("Progress")
    st.write(job.get("message") or job.get("status") or "Waiting")
    for step in job.get("trace") or []:
        state = "done" if step.get("state") == "done" else "working"
        with st.expander(
            f"{step.get('title') or 'Model'} — {state}", expanded=True
        ):
            if step.get("model"):
                st.caption(step["model"])
            if step.get("received"):
                st.markdown("**From the history rows**")
                st.code(step["received"])
            if step.get("thinking"):
                st.markdown("**Thinking**")
                st.code(step["thinking"])
            if step.get("reply"):
                st.markdown("**Reply**")
                st.code(step["reply"])
            elif state == "working":
                st.caption("Called the model. No text yet.")
    if job.get("status") in {"queued", "running"}:
        time.sleep(POLL_SECONDS)
        st.rerun()
    result = job.get("result") or {}
    if job.get("status") == "completed" and result.get("kind") == "text":
        st.subheader("Feedback")
        st.caption("Nothing is sent. The box is the text to copy.")
        feedback = result.get("text") or ""
        st.markdown(feedback)
        st.code(feedback, language=None)
    elif job.get("status") == "completed" and result.get("content_base64"):
        data = base64.b64decode(result["content_base64"])
        st.download_button(
            "Download",
            data=data,
            file_name=result["filename"],
            mime=result["media_type"],
        )
    elif job.get("status") not in {"queued", "running"}:
        st.error(job.get("error") or "The run did not finish.")


if __name__ == "__main__":
    main()
