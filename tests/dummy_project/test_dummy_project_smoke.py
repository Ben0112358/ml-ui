def test_config_paths_resolve(ml_ui_env):
    import ml_ui.config as config

    assert config.LOGS_DIR.name == "ui"
