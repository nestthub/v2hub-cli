"""Tests for v2hub_cli.cli_manager.ClientManager."""

from __future__ import annotations

import pytest

from v2hub_cli.cli_manager import ClientManager


class TestEnvHelper:
    def test_env_returns_none_when_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("V2HUB_API_URL", raising=False)
        assert ClientManager._env("V2HUB_API_URL") is None

    def test_env_returns_stripped_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("V2HUB_API_URL", "  https://api.example.com  ")
        assert ClientManager._env("V2HUB_API_URL") == "https://api.example.com"

    def test_env_returns_none_for_blank_string(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("V2HUB_API_URL", "   ")
        assert ClientManager._env("V2HUB_API_URL") is None

    def test_env_returns_none_for_empty_string(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("V2HUB_API_URL", "")
        assert ClientManager._env("V2HUB_API_URL") is None


class TestResolveBaseUrl:
    def test_explicit_value_wins_over_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("V2HUB_API_URL", "https://env.example.com")
        assert ClientManager.resolve_base_url("https://explicit.example.com") == (
            "https://explicit.example.com"
        )

    def test_falls_back_to_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("V2HUB_API_URL", "https://env.example.com")
        assert ClientManager.resolve_base_url(None) == "https://env.example.com"

    def test_none_when_neither_provided(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("V2HUB_API_URL", raising=False)
        assert ClientManager.resolve_base_url(None) is None

    def test_empty_string_falls_back_to_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("V2HUB_API_URL", "https://env.example.com")
        assert ClientManager.resolve_base_url("") == "https://env.example.com"


class TestResolveApiToken:
    def test_explicit_value_wins_over_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("V2HUB_API_TOKEN", "env-token")
        assert ClientManager.resolve_api_token("explicit-token") == "explicit-token"

    def test_falls_back_to_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("V2HUB_API_TOKEN", "env-token")
        assert ClientManager.resolve_api_token(None) == "env-token"

    def test_none_when_neither_provided(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("V2HUB_API_TOKEN", raising=False)
        assert ClientManager.resolve_api_token(None) is None


class TestResolveSecretKey:
    def test_explicit_value_wins_over_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("V2HUB_ADMIN_SECRET", "env-secret")
        assert ClientManager.resolve_secret_key("explicit-secret") == "explicit-secret"

    def test_falls_back_to_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("V2HUB_ADMIN_SECRET", "env-secret")
        assert ClientManager.resolve_secret_key(None) == "env-secret"

    def test_none_when_neither_provided(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("V2HUB_ADMIN_SECRET", raising=False)
        assert ClientManager.resolve_secret_key(None) is None


class TestGetClient:
    def test_raises_when_base_url_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("V2HUB_API_URL", raising=False)

        with (
            pytest.raises(ValueError, match="API URL not provided"),
            ClientManager.get_client(None, "token"),
        ):
            pass

    def test_raises_when_api_token_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("V2HUB_API_TOKEN", raising=False)

        with (
            pytest.raises(ValueError, match="API token not provided"),
            ClientManager.get_client("https://api.example.com", None),
        ):
            pass

    def test_base_url_error_checked_before_token_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("V2HUB_API_URL", raising=False)
        monkeypatch.delenv("V2HUB_API_TOKEN", raising=False)

        with (
            pytest.raises(ValueError, match="API URL not provided"),
            ClientManager.get_client(None, None),
        ):
            pass

    def test_yields_configured_client(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import v2hub.client as v2hub_client_module

        created = {}

        class FakeClient:
            def __init__(self, base_url: str, api_token: str) -> None:
                created["base_url"] = base_url
                created["api_token"] = api_token

            def __enter__(self) -> FakeClient:
                return self

            def __exit__(self, *exc_info: object) -> None:
                return None

        monkeypatch.setattr(v2hub_client_module, "VPNClient", FakeClient)

        with ClientManager.get_client("https://api.example.com", "secret-token") as client:
            assert isinstance(client, FakeClient)

        assert created == {"base_url": "https://api.example.com", "api_token": "secret-token"}

    def test_env_vars_used_when_args_omitted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import v2hub.client as v2hub_client_module

        monkeypatch.setenv("V2HUB_API_URL", "https://env.example.com")
        monkeypatch.setenv("V2HUB_API_TOKEN", "env-token")

        created = {}

        class FakeClient:
            def __init__(self, base_url: str, api_token: str) -> None:
                created["base_url"] = base_url
                created["api_token"] = api_token

            def __enter__(self) -> FakeClient:
                return self

            def __exit__(self, *exc_info: object) -> None:
                return None

        monkeypatch.setattr(v2hub_client_module, "VPNClient", FakeClient)

        with ClientManager.get_client(None, None):
            pass

        assert created == {"base_url": "https://env.example.com", "api_token": "env-token"}


class TestGetAdminClient:
    def test_raises_import_error_when_v2hub_admin_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import builtins

        real_import = builtins.__import__

        def fake_import(name: str, *args: object, **kwargs: object) -> object:
            if name == "v2hub_admin.client" or name.startswith("v2hub_admin"):
                raise ImportError("No module named 'v2hub_admin'")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)

        with (
            pytest.raises(ImportError, match="Admin CLI support is not installed"),
            ClientManager.get_admin_client("https://api.example.com", "secret"),
        ):
            pass

    def test_raises_when_base_url_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import sys
        import types

        fake_admin_client_mod = types.ModuleType("v2hub_admin.client")

        class FakeAdminClient:
            def __init__(self, **kwargs: object) -> None:
                self.kwargs = kwargs

            def __enter__(self) -> FakeAdminClient:
                return self

            def __exit__(self, *exc_info: object) -> None:
                return None

        fake_admin_client_mod.AdminClient = FakeAdminClient
        monkeypatch.setitem(sys.modules, "v2hub_admin", types.ModuleType("v2hub_admin"))
        monkeypatch.setitem(sys.modules, "v2hub_admin.client", fake_admin_client_mod)

        monkeypatch.delenv("V2HUB_API_URL", raising=False)

        with (
            pytest.raises(ValueError, match="API URL not provided"),
            ClientManager.get_admin_client(None, "secret"),
        ):
            pass

    def test_raises_when_secret_key_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import sys
        import types

        fake_admin_client_mod = types.ModuleType("v2hub_admin.client")

        class FakeAdminClient:
            def __init__(self, **kwargs: object) -> None:
                self.kwargs = kwargs

            def __enter__(self) -> FakeAdminClient:
                return self

            def __exit__(self, *exc_info: object) -> None:
                return None

        fake_admin_client_mod.AdminClient = FakeAdminClient
        monkeypatch.setitem(sys.modules, "v2hub_admin", types.ModuleType("v2hub_admin"))
        monkeypatch.setitem(sys.modules, "v2hub_admin.client", fake_admin_client_mod)

        monkeypatch.delenv("V2HUB_ADMIN_SECRET", raising=False)

        with (
            pytest.raises(ValueError, match="Admin secret key not provided"),
            ClientManager.get_admin_client("https://api.example.com", None),
        ):
            pass

    def test_yields_configured_admin_client(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import sys
        import types

        fake_admin_client_mod = types.ModuleType("v2hub_admin.client")
        created = {}

        class FakeAdminClient:
            def __init__(self, **kwargs: object) -> None:
                created.update(kwargs)

            def __enter__(self) -> FakeAdminClient:
                return self

            def __exit__(self, *exc_info: object) -> None:
                return None

        fake_admin_client_mod.AdminClient = FakeAdminClient
        monkeypatch.setitem(sys.modules, "v2hub_admin", types.ModuleType("v2hub_admin"))
        monkeypatch.setitem(sys.modules, "v2hub_admin.client", fake_admin_client_mod)

        with ClientManager.get_admin_client(
            "https://api.example.com", "secret-key", timeout=15.0
        ) as client:
            assert isinstance(client, FakeAdminClient)

        assert created["base_url"] == "https://api.example.com"
        assert created["secret_key"] == "secret-key"
        assert created["timeout"] == 15.0
