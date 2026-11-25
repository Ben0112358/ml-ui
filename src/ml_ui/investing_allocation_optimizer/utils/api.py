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
    """Build an http endpoint from a host and port chosen in the UI.

    Raises ValueError if the host is not 127.0.0.1, localhost, or
    serving, or if the port is not an int between 1 and 65535.
    """
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
    """Resolve the serving endpoint from the environment.

    Resolution order:

    1. ``SERVING_URL``, if non-empty, validated by ``parse_serving_base_url``.
    2. Inside a Docker container (``/.dockerenv`` exists):
       ``http://serving:8000``.
    3. Otherwise ``http://127.0.0.1:<SERVING_PORT>``, where
       ``SERVING_PORT`` defaults to 8000.

    Raises ValueError if ``SERVING_URL`` is invalid or ``SERVING_PORT``
    is not numeric.
    """
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
    """Parse and validate a serving base URL such as http://serving:8000.

    Surrounding whitespace and trailing slashes are ignored. The scheme
    must be http or https, the host must be 127.0.0.1, localhost, or
    serving, and the URL must not contain credentials, a path, a query,
    or a fragment. Without an explicit port, 80 (http) or 443 (https) is
    used.

    Raises ValueError if any of these checks fails.
    """
    return _endpoint_from_parsed_url(raw)


def _validated_job_id(job_id: str) -> str:
    if not isinstance(job_id, str) or not _JOB_ID_RE.match(job_id):
        raise ValueError("Invalid job id.")
    uuid.UUID(job_id)
    return job_id


# Back-compat for tests/imports
DEFAULT_SERVING_URL = serving_base_url()


def fetch_options(endpoint: ServingEndpoint | None = None) -> dict[str, Any]:
    """Fetch the optimizer options from ``GET /options``.

    Uses ``default_serving_endpoint()`` when ``endpoint`` is None.
    Raises requests.HTTPError on an error response.
    """
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
    """Start an optimization job with ``POST /jobs`` and return its id.

    ``payload`` is usually built with ``build_job_payload``. Uses
    ``default_serving_endpoint()`` when ``endpoint`` is None. Raises
    requests.HTTPError on an error response and ValueError if the
    returned job id is not a UUID.
    """
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
    """Return the current state of a job from ``GET /jobs/<job_id>``.

    Uses ``default_serving_endpoint()`` when ``endpoint`` is None. Raises
    ValueError if ``job_id`` is not a UUID and requests.HTTPError on an
    error response.
    """
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
    """Cancel a job with ``DELETE /jobs/<job_id>``.

    Uses ``default_serving_endpoint()`` when ``endpoint`` is None. Raises
    ValueError if ``job_id`` is not a UUID and requests.HTTPError on an
    error response.
    """
    ep = endpoint or default_serving_endpoint()
    safe_id = _validated_job_id(job_id)
    resp = requests.delete(
        ep.url_path(f"/jobs/{safe_id}"),
        timeout=30,
    )
    resp.raise_for_status()
