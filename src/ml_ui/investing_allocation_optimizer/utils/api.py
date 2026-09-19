import os
import re
import uuid
from typing import Any
from urllib.parse import urlparse

import requests

_ALLOWED_SERVING_HOSTS = frozenset({"127.0.0.1", "localhost", "serving"})
_JOB_ID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _normalize_serving_url(raw: str) -> str:
    cleaned = raw.strip().rstrip("/")
    parsed = urlparse(cleaned)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Serving base URL must use http or https.")
    if parsed.username or parsed.password:
        raise ValueError("Serving base URL must not include credentials.")
    if parsed.path not in {"", "/"}:
        raise ValueError("Serving base URL must not include a path.")
    if parsed.params or parsed.query or parsed.fragment:
        raise ValueError(
            "Serving base URL must not include query or fragment."
        )
    if not parsed.hostname:
        raise ValueError("Serving base URL must include a hostname.")
    if parsed.hostname not in _ALLOWED_SERVING_HOSTS:
        raise ValueError(
            "Serving base URL host is not allowed. "
            "Use 127.0.0.1, localhost, or serving."
        )
    port = parsed.port
    if port is not None and not (1 <= port <= 65535):
        raise ValueError("Serving base URL port is out of range.")
    if port is None:
        return f"{parsed.scheme}://{parsed.hostname}"
    return f"{parsed.scheme}://{parsed.hostname}:{port}"


def serving_base_url() -> str:
    """
    Where the UI should call ml-serving.

    - SERVING_URL: explicit override (set in UI container compose).
    - On the host: http://127.0.0.1:$SERVING_PORT (pipeline maps serving here).
    - In a container: http://serving:8000 (compose service on shared network).
    """
    explicit = os.environ.get("SERVING_URL", "").strip()
    if explicit:
        return _normalize_serving_url(explicit)

    if os.path.exists("/.dockerenv"):
        return "http://serving:8000"

    port = os.environ.get("SERVING_PORT", "8000").strip() or "8000"
    return _normalize_serving_url(f"http://127.0.0.1:{port}")


def validated_serving_base_url(base_url: str | None = None) -> str:
    """Restrict sidebar/env URLs to local homelab serving targets."""
    if base_url is None:
        return serving_base_url()
    return _normalize_serving_url(base_url)


def _validated_job_id(job_id: str) -> str:
    if not _JOB_ID_RE.match(job_id):
        raise ValueError("Invalid job id.")
    uuid.UUID(job_id)
    return job_id


# Back-compat for tests/imports
DEFAULT_SERVING_URL = serving_base_url()


def fetch_options(base_url: str | None = None) -> dict[str, Any]:
    url = validated_serving_base_url(base_url)
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
    url = validated_serving_base_url(base_url)
    resp = requests.post(
        f"{url}/jobs",
        json=payload,
        timeout=60,
    )
    resp.raise_for_status()
    job_id = resp.json()["job_id"]
    return _validated_job_id(job_id)


def poll_job(
    job_id: str,
    base_url: str | None = None,
) -> dict[str, Any]:
    url = validated_serving_base_url(base_url)
    safe_id = _validated_job_id(job_id)
    resp = requests.get(
        f"{url}/jobs/{safe_id}",
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def cancel_job(job_id: str, base_url: str | None = None) -> None:
    url = validated_serving_base_url(base_url)
    safe_id = _validated_job_id(job_id)
    requests.delete(
        f"{url}/jobs/{safe_id}",
        timeout=30,
    )
