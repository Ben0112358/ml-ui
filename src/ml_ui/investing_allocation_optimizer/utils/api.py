import os
from typing import Any

import requests


def serving_base_url() -> str:
    """
    Where the UI should call ml-serving.

    - SERVING_URL: explicit override (set in UI container compose).
    - On the host: http://127.0.0.1:$SERVING_PORT (pipeline maps serving here).
    - In a container: http://serving:8000 (compose service on shared network).
    """
    explicit = os.environ.get("SERVING_URL", "").strip()
    if explicit:
        return explicit.rstrip("/")

    if os.path.exists("/.dockerenv"):
        return "http://serving:8000"

    port = os.environ.get("SERVING_PORT", "8000").strip() or "8000"
    return f"http://127.0.0.1:{port}"


# Back-compat for tests/imports
DEFAULT_SERVING_URL = serving_base_url()


def fetch_options(base_url: str | None = None) -> dict[str, Any]:
    url = (base_url or serving_base_url()).rstrip("/")
    resp = requests.get(f"{url}/options", timeout=30)
    resp.raise_for_status()
    return resp.json()


def build_job_payload(
    metric: str,
    horizon_years: float,
    n_bootstrap_paths: int,
    n_trials: int,
    random_seed: int | None,
    bootstrap_block_size: str | int,
    p_1_constraint: float | None,
    p_5_constraint: float | None,
    max_std: float | None,
    weight_bounds: dict[str, dict[str, float]] | None,
    metric_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "metric": metric,
        "horizon_years": horizon_years,
        "n_bootstrap_paths": n_bootstrap_paths,
        "n_trials": n_trials,
        "bootstrap_block_size": bootstrap_block_size,
    }
    if random_seed is not None:
        payload["random_seed"] = random_seed
    if p_1_constraint is not None:
        payload["p_1_constraint"] = p_1_constraint
    if p_5_constraint is not None:
        payload["p_5_constraint"] = p_5_constraint
    if max_std is not None:
        payload["max_std"] = max_std
    if weight_bounds:
        payload["weight_bounds"] = weight_bounds
    if metric_params:
        payload["metric_params"] = metric_params
    return payload


def start_job(
    payload: dict[str, Any],
    base_url: str | None = None,
) -> str:
    url = (base_url or serving_base_url()).rstrip("/")
    resp = requests.post(
        f"{url}/jobs",
        json=payload,
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["job_id"]


def poll_job(
    job_id: str,
    base_url: str | None = None,
) -> dict[str, Any]:
    url = (base_url or serving_base_url()).rstrip("/")
    resp = requests.get(
        f"{url}/jobs/{job_id}",
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def cancel_job(job_id: str, base_url: str | None = None) -> None:
    url = (base_url or serving_base_url()).rstrip("/")
    requests.delete(
        f"{url}/jobs/{job_id}",
        timeout=30,
    )
