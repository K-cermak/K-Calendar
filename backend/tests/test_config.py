from pathlib import Path

import pytest

from app.config import ConfigError, Settings, load_settings

BASE = "https://calendar.example.com"


@pytest.fixture(autouse=True)
def _data_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path / "data"))


def test_base_url_is_the_only_required_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APP_BASE_URL", raising=False)
    with pytest.raises(ConfigError, match="APP_BASE_URL: is required"):
        load_settings()
    monkeypatch.setenv("APP_BASE_URL", BASE)
    settings = load_settings()
    assert not settings.smtp_enabled
    assert not settings.oidc_enabled
    assert settings.session_days == 180


def test_base_url_must_be_absolute(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_BASE_URL", "calendar.example.com")
    with pytest.raises(ConfigError, match="APP_BASE_URL"):
        load_settings()


def test_base_url_must_not_have_a_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_BASE_URL", "https://example.com/calendar")
    with pytest.raises(ConfigError, match="APP_BASE_URL: must not contain a path"):
        load_settings()


def test_base_url_trailing_slash_is_dropped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_BASE_URL", BASE + "/")
    settings = load_settings()
    assert settings.base_url == BASE
    assert settings.secure_cookies


def test_password_login_off_requires_oidc(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_BASE_URL", BASE)
    monkeypatch.setenv("APP_PASSWORD_LOGIN_ENABLED", "false")
    with pytest.raises(ConfigError, match="requires OIDC"):
        load_settings()
    monkeypatch.setenv("APP_OIDC_DISCOVERY_URL", "https://id.example.com/.well-known/openid-configuration")
    monkeypatch.setenv("APP_OIDC_CLIENT_ID", "calendar")
    monkeypatch.setenv("APP_OIDC_CLIENT_SECRET", "secret")
    assert load_settings().oidc_enabled


def test_partial_oidc_names_what_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_BASE_URL", BASE)
    monkeypatch.setenv("APP_OIDC_CLIENT_ID", "calendar")
    with pytest.raises(ConfigError, match="missing APP_OIDC_DISCOVERY_URL, APP_OIDC_CLIENT_SECRET"):
        load_settings()


def test_smtp_host_needs_a_sender(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_BASE_URL", BASE)
    monkeypatch.setenv("APP_SMTP_HOST", "mail.example.com")
    with pytest.raises(ConfigError, match="APP_SMTP_FROM is required"):
        load_settings()
    monkeypatch.setenv("APP_SMTP_FROM", "calendar@example.com")
    assert load_settings().smtp_enabled


def test_smtp_security_is_one_of_three(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_BASE_URL", BASE)
    monkeypatch.setenv("APP_SMTP_SECURITY", "tls")
    with pytest.raises(ConfigError, match="APP_SMTP_SECURITY"):
        load_settings()
    monkeypatch.setenv("APP_SMTP_SECURITY", "SSL")
    assert load_settings().smtp_security == "ssl"


def test_vapid_keys_go_together(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_BASE_URL", BASE)
    monkeypatch.setenv("APP_VAPID_PUBLIC_KEY", "abc")
    with pytest.raises(ConfigError, match="set both or neither"):
        load_settings()


def test_trusted_proxies_are_comma_separated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_BASE_URL", BASE)
    monkeypatch.setenv("APP_TRUSTED_PROXIES", "10.0.0.1, 172.16.0.0/12")
    assert load_settings().trusted_proxies == ["10.0.0.1", "172.16.0.0/12"]


def test_trusted_proxies_must_be_addresses(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_BASE_URL", BASE)
    monkeypatch.setenv("APP_TRUSTED_PROXIES", "10.0.0.1, proxy.local")
    with pytest.raises(ConfigError, match=r"APP_TRUSTED_PROXIES: 'proxy\.local' is not an IP address"):
        load_settings()


def test_session_days_must_be_positive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_BASE_URL", BASE)
    monkeypatch.setenv("APP_SESSION_DAYS", "0")
    with pytest.raises(ConfigError, match="APP_SESSION_DAYS: must be at least 1"):
        load_settings()


def test_every_problem_is_listed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_BASE_URL", BASE)
    monkeypatch.setenv("APP_SESSION_DAYS", "ten")
    monkeypatch.setenv("APP_LOG_LEVEL", "loud")
    with pytest.raises(ConfigError, match=r"(?s)APP_SESSION_DAYS: .*integer.*APP_LOG_LEVEL: "):
        load_settings()


def test_secret_key_must_not_be_short(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_BASE_URL", BASE)
    monkeypatch.setenv("APP_SECRET_KEY", "hunter2")
    with pytest.raises(ConfigError, match="APP_SECRET_KEY: must be at least 32 characters"):
        load_settings()


def test_data_dir_must_be_writable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("APP_BASE_URL", BASE)
    blocked = tmp_path / "file"
    blocked.write_text("")
    monkeypatch.setenv("APP_DATA_DIR", str(blocked / "data"))
    with pytest.raises(ConfigError, match="APP_DATA_DIR: cannot write to"):
        load_settings()


def test_secret_key_is_generated_once(tmp_path: Path) -> None:
    first = Settings(base_url="http://x", data_dir=tmp_path).resolved_secret_key
    second = Settings(base_url="http://x", data_dir=tmp_path).resolved_secret_key
    assert first == second
    assert (tmp_path / "secret.key").stat().st_mode & 0o777 == 0o600


def test_configured_secret_key_wins(tmp_path: Path) -> None:
    key = "configured-" + "k" * 32
    settings = Settings(base_url="http://x", data_dir=tmp_path, secret_key=key)
    assert settings.resolved_secret_key == key
    assert not (tmp_path / "secret.key").exists()
