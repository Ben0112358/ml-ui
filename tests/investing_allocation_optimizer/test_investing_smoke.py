import pytest

from ml_ui.investing_allocation_optimizer.utils.api import (
    build_job_payload,
    endpoint_from_host_port,
    serving_base_url,
)
from ml_ui.investing_allocation_optimizer.utils.format import (
    comparison_stats_table,
    weights_dataframe,
)


def test_serving_base_url_local_default(monkeypatch):
    monkeypatch.delenv("SERVING_URL", raising=False)
    monkeypatch.delenv("SERVING_PORT", raising=False)
    monkeypatch.setattr(
        "ml_ui.investing_allocation_optimizer.utils.api.os.path.exists",
        lambda _p: False,
    )
    assert serving_base_url() == "http://127.0.0.1:8000"


def test_endpoint_from_host_port_allows_pipeline_port():
    ep = endpoint_from_host_port("127.0.0.1", 33044)
    assert ep.url_path("/options") == "http://127.0.0.1:33044/options"


def test_endpoint_rejects_untrusted_host():
    with pytest.raises(ValueError, match="not allowed"):
        endpoint_from_host_port("169.254.169.254", 8000)


def test_build_job_payload_minimal():
    body = build_job_payload(
        metric="sharpe",
        horizon_years=10.0,
        n_bootstrap_paths=500,
        n_trials=50,
        random_seed=None,
        bootstrap_block_size="cube root",
        p_1_constraint=None,
        p_5_constraint=None,
        max_std=None,
        weight_bounds=None,
    )
    assert body["metric"] == "sharpe"
    assert "random_seed" not in body


def test_format_comparison_table():
    result = {
        "benchmark_label": "total-world",
        "stats": {"sharpe": 0.5, "mean_cagr": 0.07},
        "benchmark_stats": {"sharpe": 0.4, "mean_cagr": 0.06},
    }
    df = comparison_stats_table(result)
    assert "optimal" in df.columns
    sharpe_row = df.loc[df["metric"] == "Sharpe"].iloc[0]
    assert sharpe_row["optimal"] == 0.5
    assert sharpe_row["100% total-world"] == 0.4


def test_weights_dataframe():
    df = weights_dataframe({"total-world": 0.6, "growth": 0.4})
    assert df["weight"].sum() == 1.0
