import os
import re
import uuid
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import urlparse

import requests

AllowedHost = Literal["127.0.0.1", "localhost", "serving"]
_ALLOWED_SERVING_HOSTS: frozenset[str] = frozenset(
    {"127.0.0.1", "localhost", "serving"}
)
_JOB_ID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ServingEndpoint:
    """Fixed scheme/host/port used to build outbound serving URLs."""

    scheme: Literal["http", "https"]
    host: AllowedHost
    port: int

    def origin(self) -> str:
        return f"{self.scheme}://{self.host}:{self.port}"

    def url_path(self, path: str) -> str:
        if not path.startswith("/") or "://" in path:
            raise ValueError("Invalid serving path.")
        return f"{self.origin()}{path}"


def endpoint_from_host_port(host: str, port: int) -> ServingEndpoint:
    if host not in _ALLOWED_SERVING_HOSTS:
        raise ValueError(
            "Serving host is not allowed. "
            "Use 127.0.0.1, localhost, or serving."
        )
    if not isinstance(port, int) or not (1 <= port <= 65535):
        raise ValueError("Serving port must be between 1 and 65535.")
    scheme: Literal["http", "https"] = "http"
    return ServingEndpoint(scheme, host, port)  # type: ignore[arg-type]


def _endpoint_from_parsed_url(raw: str) -> ServingEndpoint:
    cleaned = raw.strip().rstrip("/")
    parsed = urlparse(cleaned)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Serving URL must use http or https.")
    if parsed.username or parsed.password:
        raise ValueError("Serving URL must not include credentials.")
    if parsed.path not in {"", "/"}:
        raise ValueError("Serving URL must not include a path.")
    if parsed.params or parsed.query or parsed.fragment:
        raise ValueError("Serving URL must not include query or fragment.")
    if not parsed.hostname or parsed.hostname not in _ALLOWED_SERVING_HOSTS:
        raise ValueError(
            "Serving URL host is not allowed. "
            "Use 127.0.0.1, localhost, or serving."
        )
    port = parsed.port
    if port is None:
        port = 443 if parsed.scheme == "https" else 80
    if not (1 <= port <= 65535):
        raise ValueError("Serving port is out of range.")
    scheme: Literal["http", "https"] = parsed.scheme  # type: ignore
    host: AllowedHost = parsed.hostname  # type: ignore
    return ServingEndpoint(scheme, host, port)


def default_serving_endpoint() -> ServingEndpoint:
    explicit = os.environ.get("SERVING_URL", "").strip()
    if explicit:
        return _endpoint_from_parsed_url(explicit)
    if os.path.exists("/.dockerenv"):
        return endpoint_from_host_port("serving", 8000)
    port_str = os.environ.get("SERVING_PORT", "8000").strip() or "8000"
    if not port_str.isdigit():
        raise ValueError("SERVING_PORT must be numeric.")
    return endpoint_from_host_port("127.0.0.1", int(port_str))


def serving_base_url() -> str:
    return default_serving_endpoint().origin()


def parse_serving_base_url(raw: str) -> ServingEndpoint:
    return _endpoint_from_parsed_url(raw)


def _validated_job_id(job_id: str) -> str:
    if not _JOB_ID_RE.match(job_id):
        raise ValueError("Invalid job id.")
    uuid.UUID(job_id)
    return job_id


# Back-compat for tests/imports
DEFAULT_SERVING_URL = serving_base_url()


def fetch_options(endpoint: ServingEndpoint | None = None) -> dict[str, Any]:
    ep = endpoint or default_serving_endpoint()
    resp = requests.get(ep.url_path("/options"), timeout=30)
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
    endpoint: ServingEndpoint | None = None,
) -> str:
    ep = endpoint or default_serving_endpoint()
    resp = requests.post(
        ep.url_path("/jobs"),
        json=payload,
        timeout=60,
    )
    resp.raise_for_status()
    job_id = resp.json()["job_id"]
    return _validated_job_id(job_id)


def poll_job(
    job_id: str,
    endpoint: ServingEndpoint | None = None,
) -> dict[str, Any]:
    ep = endpoint or default_serving_endpoint()
    safe_id = _validated_job_id(job_id)
    resp = requests.get(
        ep.url_path(f"/jobs/{safe_id}"),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def cancel_job(
    job_id: str,
    endpoint: ServingEndpoint | None = None,
) -> None:
    ep = endpoint or default_serving_endpoint()
    safe_id = _validated_job_id(job_id)
    requests.delete(
        ep.url_path(f"/jobs/{safe_id}"),
        timeout=30,
    )
