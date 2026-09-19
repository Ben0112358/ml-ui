import ast


def test_investing_predict_json_matches_serving_schema():
    default = """{
        "data": {
            "metric": "mean",
            "p_1_constraint": 0,
            "p_5_constraint": 0,
            "max_std": 0,
            "n_trials": 100,
            "random_seed": 0,
            "bootstrap_block_size": "cube root",
            "bootstrap_path_length": 100,
            "n_bootstrap_paths": 1000
        }
    }"""
    body = ast.literal_eval(default)
    assert isinstance(body["data"], dict)
    assert "metric" in body["data"]
    assert "data" not in body["data"]
