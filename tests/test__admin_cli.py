"""Tests for v2hub_cli._admin_cli.

Tests admin commands through typer's CliRunner with a mocked AdminClient.
"""

from __future__ import annotations

import types
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest
import typer
from typer.testing import CliRunner

from v2hub_admin import AdminClient
from v2hub_cli import _admin_cli

if TYPE_CHECKING:
    from collections.abc import Iterator


runner = CliRunner()


@pytest.fixture
def admin_app() -> typer.Typer:
    app = typer.Typer(name="admin")
    _admin_cli.register_admin_commands(app)
    return app


def _patch_admin_client(
    monkeypatch: pytest.MonkeyPatch,
    client: MagicMock,
) -> None:
    @contextmanager
    def fake_get_admin_client(
        base_url: str | None,
        secret_key: str | None,
        timeout: float = 30.0,
    ) -> Iterator[MagicMock]:
        yield client

    monkeypatch.setattr(_admin_cli, "get_admin_client", fake_get_admin_client)


class TestShortHelper:
    def test_returns_original_when_short_enough(self) -> None:
        assert _admin_cli.short("abc", 12) == "abc"

    def test_truncates_long_value(self) -> None:
        result = _admin_cli.short("abcdefghijklmnop", 10)
        assert result.endswith("…")
        assert len(result) == 10

    def test_n_at_or_below_three_returns_unchanged(self) -> None:
        assert _admin_cli.short("abcdef", 3) == "abcdef"


class TestAdminVersionCommand:
    def test_shows_version(self, admin_app: typer.Typer) -> None:
        result = runner.invoke(admin_app, ["version"])

        assert result.exit_code == 0
        assert _admin_cli.ADMIN_CLI_AVAILABLE is True


class TestCreateUserCommand:
    def test_creates_user(
        self,
        monkeypatch: pytest.MonkeyPatch,
        admin_app: typer.Typer,
    ) -> None:
        client = MagicMock(spec=AdminClient)
        client.create_user.return_value = types.SimpleNamespace(
            api_token="new-api-token",
            user_hash="hash123",
        )

        _patch_admin_client(monkeypatch, client)

        result = runner.invoke(admin_app, ["create-user", "42"])

        assert result.exit_code == 0
        assert "new-api-token" in result.stdout
        assert "hash123" in result.stdout

        client.create_user.assert_called_once_with(42)

    def test_value_error_exits_nonzero(
        self,
        monkeypatch: pytest.MonkeyPatch,
        admin_app: typer.Typer,
    ) -> None:
        @contextmanager
        def fake_get_admin_client(*args: Any, **kwargs: Any) -> Iterator[Any]:
            raise ValueError("bad config")
            yield  # pragma: no cover

        monkeypatch.setattr(
            _admin_cli,
            "get_admin_client",
            fake_get_admin_client,
        )

        result = runner.invoke(admin_app, ["create-user", "42"])

        assert result.exit_code == 1
        assert "bad config" in result.stdout


class TestGetUserCommand:
    def test_gets_user(
        self,
        monkeypatch: pytest.MonkeyPatch,
        admin_app: typer.Typer,
    ) -> None:
        client = MagicMock(spec=AdminClient)
        client.get_user.return_value = types.SimpleNamespace(
            user_id=42,
            is_active=True,
            api_token="tok",
        )

        _patch_admin_client(monkeypatch, client)

        result = runner.invoke(admin_app, ["get-user", "42"])

        assert result.exit_code == 0
        assert "True" in result.stdout

        client.get_user.assert_called_once_with(42)


class TestDeleteUserCommand:
    def test_deletes_user(
        self,
        monkeypatch: pytest.MonkeyPatch,
        admin_app: typer.Typer,
    ) -> None:
        client = MagicMock(spec=AdminClient)

        _patch_admin_client(monkeypatch, client)

        result = runner.invoke(admin_app, ["delete-user", "42"])

        assert result.exit_code == 0
        assert "Deleted" in result.stdout

        client.delete_user.assert_called_once_with(42)


class TestBanIpCommand:
    def test_bans_ip(
        self,
        monkeypatch: pytest.MonkeyPatch,
        admin_app: typer.Typer,
    ) -> None:
        client = MagicMock(spec=AdminClient)

        client.ban_ip.return_value = types.SimpleNamespace(
            ban_id="ban1",
            banned_until="2026-01-01",
            remaining_seconds=3600,
        )

        _patch_admin_client(monkeypatch, client)

        result = runner.invoke(
            admin_app,
            ["ban-ip", "1.2.3.4", "--duration", "3600"],
        )

        assert result.exit_code == 0
        assert "1.2.3.4" in result.stdout
        assert "ban1" in result.stdout

        client.ban_ip.assert_called_once_with("1.2.3.4", 3600)


class TestUnbanIpCommand:
    def test_unbans_ip(
        self,
        monkeypatch: pytest.MonkeyPatch,
        admin_app: typer.Typer,
    ) -> None:
        client = MagicMock(spec=AdminClient)

        client.unban_ip.return_value = types.SimpleNamespace(
            ip_address="1.2.3.4",
            was_banned=True,
        )

        _patch_admin_client(monkeypatch, client)

        result = runner.invoke(admin_app, ["unban-ip", "1.2.3.4"])

        assert result.exit_code == 0
        assert "1.2.3.4" in result.stdout

        client.unban_ip.assert_called_once_with("1.2.3.4")


class TestBanStatusCommand:
    def test_shows_banned_status(
        self,
        monkeypatch: pytest.MonkeyPatch,
        admin_app: typer.Typer,
    ) -> None:
        client = MagicMock(spec=AdminClient)

        client.get_ban_status.return_value = types.SimpleNamespace(
            is_banned=True,
            banned_until="2026-01-01",
            remaining_seconds=100,
        )

        _patch_admin_client(monkeypatch, client)

        result = runner.invoke(
            admin_app,
            ["ban-status", "1.2.3.4"],
        )

        assert result.exit_code == 0
        assert "1.2.3.4" in result.stdout


class TestBanListCommand:
    def test_empty_list_shows_message(
        self,
        monkeypatch: pytest.MonkeyPatch,
        admin_app: typer.Typer,
    ) -> None:
        client = MagicMock(spec=AdminClient)

        client.get_ban_list.return_value = types.SimpleNamespace(
            entries=[],
            total=0,
        )

        _patch_admin_client(monkeypatch, client)

        result = runner.invoke(admin_app, ["ban-list"])

        assert result.exit_code == 0
        assert "No banned IPs found" in result.stdout

    def test_populated_list(
        self,
        monkeypatch: pytest.MonkeyPatch,
        admin_app: typer.Typer,
    ) -> None:
        client = MagicMock(spec=AdminClient)

        entry = types.SimpleNamespace(
            ip_address="1.2.3.4",
            ban_id="ban-abc-123",
            banned_until="2026-01-01",
            remaining_seconds=42,
        )

        client.get_ban_list.return_value = types.SimpleNamespace(
            entries=[entry],
            total=1,
        )

        _patch_admin_client(monkeypatch, client)

        result = runner.invoke(admin_app, ["ban-list"])

        assert result.exit_code == 0
        assert "1.2.3.4" in result.stdout


class TestWhitelistCommands:
    def test_adds_to_whitelist(
        self,
        monkeypatch: pytest.MonkeyPatch,
        admin_app: typer.Typer,
    ) -> None:
        client = MagicMock(spec=AdminClient)

        client.add_to_whitelist.return_value = types.SimpleNamespace(message="added")

        _patch_admin_client(monkeypatch, client)

        result = runner.invoke(
            admin_app,
            ["whitelist-add", "10.0.0.0/8", "-d", "internal net"],
        )

        assert result.exit_code == 0
        assert "10.0.0.0/8" in result.stdout

        client.add_to_whitelist.assert_called_once_with(
            "10.0.0.0/8",
            "internal net",
        )

    def test_removes_from_whitelist(
        self,
        monkeypatch: pytest.MonkeyPatch,
        admin_app: typer.Typer,
    ) -> None:
        client = MagicMock(spec=AdminClient)

        client.remove_from_whitelist.return_value = types.SimpleNamespace(
            ip_address="10.0.0.0/8",
            was_whitelisted=True,
        )

        _patch_admin_client(monkeypatch, client)

        result = runner.invoke(
            admin_app,
            ["whitelist-remove", "10.0.0.0/8"],
        )

        assert result.exit_code == 0

        client.remove_from_whitelist.assert_called_once_with("10.0.0.0/8")

    def test_empty_whitelist(
        self,
        monkeypatch: pytest.MonkeyPatch,
        admin_app: typer.Typer,
    ) -> None:
        client = MagicMock(spec=AdminClient)

        client.list_whitelist.return_value = types.SimpleNamespace(
            entries=[],
            total=0,
        )

        _patch_admin_client(monkeypatch, client)

        result = runner.invoke(admin_app, ["whitelist-list"])

        assert result.exit_code == 0
        assert "No whitelist entries found" in result.stdout


class TestAdminUnavailable:
    def test_register_returns_false_and_stubs_version(self) -> None:
        app = typer.Typer(name="admin")

        original_available = _admin_cli.ADMIN_CLI_AVAILABLE

        try:
            _admin_cli.ADMIN_CLI_AVAILABLE = False

            registered = _admin_cli.register_admin_commands(app)

            assert registered is False

            result = runner.invoke(app, input="version")

            assert result.exit_code == 1
            assert "not available" in result.stdout

        finally:
            _admin_cli.ADMIN_CLI_AVAILABLE = original_available
