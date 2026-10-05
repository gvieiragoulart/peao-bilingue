from vanhack_watcher.config import Settings


def test_settings_load_defaults():
    settings = Settings(_env_file=None)
    assert settings.vanhack_login_url == "https://auth.vanhack.com"
    assert settings.timezone == "America/Sao_Paulo"
    assert settings.max_details_per_run == 15
