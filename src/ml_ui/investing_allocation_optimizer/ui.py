import logging
import time

import streamlit as st

from ml_ui.investing_allocation_optimizer.utils.api import (
    build_job_payload,
    cancel_job,
    fetch_options,
    poll_job,
    serving_base_url,
    start_job,
)
from ml_ui.investing_allocation_optimizer.utils.format import (
    comparison_stats_table,
    history_dataframe,
    weights_dataframe,
)
from ml_ui.utils import setup_logging

POLL_SECONDS = 0.5


def _sanitize_for_log(value: object) -> str:
    return str(value).replace("\r", "").replace("\n", "")


# (selectbox key, label, value sent to serving)
_BLOCK_SIZE_OPTIONS: list[tuple[str, str, str | int]] = [
    ("cube root", "Cube root of sample length", "cube root"),
    ("5", "5 periods", 5),
    ("10", "10 periods", 10),
    ("12", "12 periods", 12),
    ("20", "20 periods", 20),
    ("36", "36 periods", 36),
    ("52", "52 periods", 52),
]


def _metric_labels(metrics: list[dict]) -> dict[str, str]:
    return {m["key"]: m.get("label", m["key"]) for m in metrics}


def main() -> None:
    setup_logging()
    logger = logging.getLogger(__name__)
    st.set_page_config(
        page_title="Allocation optimizer",
        layout="wide",
    )
    st.title("Investing allocation optimizer")
    st.caption("Stationary bootstrap paths + Optuna.")

    with st.sidebar:
        st.header("Connection")
        default_url = st.session_state.get(
            "serving_url",
            serving_base_url(),
        )
        serving_url = st.text_input(
            "Serving base URL",
            value=default_url,
            help=(
                "Local Streamlit: http://127.0.0.1:<port> (see pipeline "
                "Serving URL). UI container: http://serving:8000."
            ),
        ).rstrip("/")
        st.session_state["serving_url"] = serving_url

        st.header("Optimization")

    try:
        options = fetch_options(serving_url)
    except Exception as exc:
        st.error(f"Could not load options from serving: {exc}")
        st.info(
            "Start **ml-serving** (same compose network or mapped port), "
            "then set **Serving base URL** in the sidebar—for example "
            "`http://127.0.0.1:33044` from `execute.sh` output."
        )
        st.stop()

    metrics = options.get("metrics", [])
    assets = options.get("assets", [])
    defaults = options.get("defaults", {})
    sample_window = options.get("sample_window")
    if sample_window:
        st.info(
            f"Training sample: {sample_window.get('start')} → "
            f"{sample_window.get('end')} "
            f"({sample_window.get('rows')} rows)"
        )

    metric_keys = [m["key"] for m in metrics]
    labels = _metric_labels(metrics)

    with st.sidebar:
        default_metric = defaults.get("metric", "mean_return")
        metric_idx = (
            metric_keys.index(default_metric)
            if default_metric in metric_keys
            else 0
        )
        metric = st.selectbox(
            "Objective",
            metric_keys,
            index=metric_idx,
            format_func=lambda k: labels.get(k, k),
        )
        selected = next((m for m in metrics if m["key"] == metric), {})
        if selected.get("description"):
            st.caption(selected["description"])

        metric_params = None

        horizon_years = st.number_input(
            "Horizon (years)",
            value=float(defaults.get("horizon_years", 10.0)),
            min_value=1.0,
            max_value=50.0,
        )
        n_bootstrap_paths = st.number_input(
            "Bootstrap paths",
            value=int(defaults.get("n_bootstrap_paths", 1000)),
            min_value=50,
            max_value=20000,
            step=50,
        )
        n_trials = st.number_input(
            "Optuna trials",
            value=int(defaults.get("n_trials", 100)),
            min_value=5,
            max_value=2000,
        )
        block_default = defaults.get("bootstrap_block_size", "cube root")
        block_keys = [o[0] for o in _BLOCK_SIZE_OPTIONS]
        block_labels = {o[0]: o[1] for o in _BLOCK_SIZE_OPTIONS}
        block_values = {o[0]: o[2] for o in _BLOCK_SIZE_OPTIONS}
        if block_default == "cube root":
            block_idx_key = "cube root"
        else:
            block_idx_key = str(int(block_default))
        if block_idx_key not in block_keys:
            block_idx_key = "cube root"
        picked_block = st.selectbox(
            "Bootstrap block size",
            options=block_keys,
            index=block_keys.index(block_idx_key),
            format_func=lambda k: block_labels[k],
        )
        bootstrap_block_size = block_values[picked_block]

        use_seed = st.checkbox("Fixed random seed", value=False)
        random_seed = st.number_input("Seed", value=42, disabled=not use_seed)
        seed_val = int(random_seed) if use_seed else None

        with st.expander("Outcome constraints"):
            use_p1 = st.checkbox("Min P1 terminal return", value=False)
            p1 = st.number_input(
                "P1 lower bound", value=0.0, disabled=not use_p1
            )
            use_p5 = st.checkbox("Min P5 terminal return", value=False)
            p5 = st.number_input(
                "P5 lower bound", value=0.0, disabled=not use_p5
            )
            use_std = st.checkbox("Max terminal std", value=False)
            max_std = st.number_input(
                "Max std", value=1.0, disabled=not use_std
            )

        with st.expander("Per-asset weight bounds"):
            weight_bounds: dict[str, dict[str, float]] = {}
            for asset in assets:
                c1, c2 = st.columns(2)
                with c1:
                    lo = st.number_input(
                        f"{asset} min",
                        min_value=0.0,
                        max_value=1.0,
                        value=0.0,
                        key=f"lo_{asset}",
                    )
                with c2:
                    hi = st.number_input(
                        f"{asset} max",
                        min_value=0.0,
                        max_value=1.0,
                        value=1.0,
                        key=f"hi_{asset}",
                    )
                if lo > hi:
                    st.warning(f"{asset}: min > max")
                elif lo > 0.0 or hi < 1.0:
                    weight_bounds[asset] = {"min": lo, "max": hi}

    run_col, cancel_col = st.columns([1, 1])
    with run_col:
        run_clicked = st.button("Run optimization", type="primary")
    with cancel_col:
        cancel_clicked = st.button("Cancel running job")

    if cancel_clicked and st.session_state.get("job_id"):
        try:
            cancel_job(st.session_state["job_id"], serving_url)
            st.warning("Cancellation requested.")
        except Exception as exc:
            st.error(str(exc))

    progress_bar = st.progress(0.0)
    status_slot = st.empty()
    chart_slot = st.empty()

    if run_clicked:
        payload = build_job_payload(
            metric=metric,
            horizon_years=horizon_years,
            n_bootstrap_paths=int(n_bootstrap_paths),
            n_trials=int(n_trials),
            random_seed=seed_val,
            bootstrap_block_size=bootstrap_block_size,
            p_1_constraint=p1 if use_p1 else None,
            p_5_constraint=p5 if use_p5 else None,
            max_std=max_std if use_std else None,
            weight_bounds=weight_bounds or None,
            metric_params=metric_params,
        )
        try:
            job_id = start_job(payload, serving_url)
            st.session_state["job_id"] = job_id
            logger.info("Started job %s", _sanitize_for_log(job_id))
        except Exception as exc:
            st.error(f"Failed to start job: {exc}")
            st.stop()

    job_id = st.session_state.get("job_id")
    if job_id:
        job = poll_job(job_id, serving_url)
        done = job.get("trials_done", 0)
        total = job.get("n_trials", 1)
        progress_bar.progress(min(1.0, done / max(total, 1)))
        status_slot.write(
            f"Status: **{job.get('status')}** — "
            f"trials {done}/{total}, "
            f"best: {job.get('best_value')}"
        )
        hist_df = history_dataframe(job.get("history") or [])
        if not hist_df.empty:
            chart_slot.line_chart(hist_df.set_index("trial")[["best_value"]])

        while job.get("status") == "running":
            time.sleep(POLL_SECONDS)
            job = poll_job(job_id, serving_url)
            done = job.get("trials_done", 0)
            progress_bar.progress(min(1.0, done / max(total, 1)))
            status_slot.write(
                f"Status: **{job.get('status')}** — "
                f"trials {done}/{total}, "
                f"best: {job.get('best_value')}"
            )
            hist_df = history_dataframe(job.get("history") or [])
            if not hist_df.empty:
                chart_slot.line_chart(
                    hist_df.set_index("trial")[["best_value"]]
                )

        if job.get("status") == "completed" and job.get("result"):
            result = job["result"]
            st.subheader("Optimal allocation")
            st.metric("Objective value", result.get("metric_value"))
            wdf = weights_dataframe(result.get("weights", {}))
            st.dataframe(wdf, use_container_width=True)
            st.bar_chart(wdf.set_index("asset"))

            st.subheader("Bootstrap statistics")
            cmp = comparison_stats_table(result)
            st.dataframe(cmp, use_container_width=True)
        elif job.get("status") == "failed":
            st.error(job.get("error") or "Optimization failed")
        elif job.get("status") == "cancelled":
            st.warning("Job cancelled.")


if __name__ == "__main__":
    main()
