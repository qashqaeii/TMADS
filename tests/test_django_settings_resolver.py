import pytest


@pytest.mark.parametrize(
    "env,expected",
    [
        ({}, "config.settings.local"),
        ({"APP_ENV": "LOCAL"}, "config.settings.local"),
        ({"APP_ENV": "PRODUCTION"}, "config.settings.production"),
        (
            {"APP_ENV": "PRODUCTION", "DJANGO_SETTINGS_MODULE": "config.settings.local"},
            "config.settings.production",
        ),
        (
            {"APP_ENV": "PRODUCTION", "DJANGO_SETTINGS_MODULE": "config.settings.production"},
            "config.settings.production",
        ),
        (
            {"APP_ENV": "LOCAL", "DJANGO_SETTINGS_MODULE": "config.settings.production"},
            "config.settings.production",
        ),
    ],
)
def test_resolve_django_settings_module(monkeypatch, env, expected):
    monkeypatch.delenv("DJANGO_SETTINGS_MODULE", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    from config.django_settings import resolve_django_settings_module

    assert resolve_django_settings_module() == expected
