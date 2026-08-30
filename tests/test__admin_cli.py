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

from v2hub.core.exceptions import VPNAPIError
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


class TestGetProviderByNameCommand:
    def test_gets_provider(
        self,
        monkeypatch: pytest.MonkeyPatch,
        admin_app: typer.Typer,
    ) -> None:
        client = MagicMock(spec=AdminClient)
        client.get_provider_by_name.return_value = types.SimpleNamespace(
            provider_hash="hash-1",
            owner_hash="owner-1",
            provider_name="vpn123",
            provider_url="https://vpn123.example.com",
            is_active=True,
            api_token="provider-token",
        )

        _patch_admin_client(monkeypatch, client)

        result = runner.invoke(admin_app, ["get-provider-by-name", "vpn123"])

        assert result.exit_code == 0
        assert "vpn123" in result.stdout
        assert "provider-token" in result.stdout
        client.get_provider_by_name.assert_called_once_with("vpn123")

    def test_error_shown_on_failure(
        self,
        monkeypatch: pytest.MonkeyPatch,
        admin_app: typer.Typer,
    ) -> None:
        client = MagicMock(spec=AdminClient)
        client.get_provider_by_name.side_effect = VPNAPIError("not found")

        _patch_admin_client(monkeypatch, client)

        result = runner.invoke(admin_app, ["get-provider-by-name", "ghost"])

        assert result.exit_code == 1


class TestGetProviderByOwnerIdCommand:
    def test_gets_provider(
        self,
        monkeypatch: pytest.MonkeyPatch,
        admin_app: typer.Typer,
    ) -> None:
        client = MagicMock(spec=AdminClient)
        client.get_provider_by_owner_id.return_value = types.SimpleNamespace(
            provider_hash="hash-1",
            owner_hash="owner-1",
            provider_name="vpn123",
            provider_url="https://vpn123.example.com",
            is_active=True,
            api_token="provider-token",
        )

        _patch_admin_client(monkeypatch, client)

        result = runner.invoke(admin_app, ["get-provider-by-owner-id", "42"])

        assert result.exit_code == 0
        assert "vpn123" in result.stdout
        client.get_provider_by_owner_id.assert_called_once_with(42)

    def test_error_shown_on_failure(
        self,
        monkeypatch: pytest.MonkeyPatch,
        admin_app: typer.Typer,
    ) -> None:
        client = MagicMock(spec=AdminClient)
        client.get_provider_by_owner_id.side_effect = VPNAPIError("not found")

        _patch_admin_client(monkeypatch, client)

        result = runner.invoke(admin_app, ["get-provider-by-owner-id", "42"])

        assert result.exit_code == 1


class TestGetUserProvidersCommand:
    def test_lists_connections(
        self,
        monkeypatch: pytest.MonkeyPatch,
        admin_app: typer.Typer,
    ) -> None:
        client = MagicMock(spec=AdminClient)
        client.get_user_providers.return_value = types.SimpleNamespace(
            connections=[
                types.SimpleNamespace(
                    provider_name="vpn123",
                    provider_url="https://vpn123.example.com",
                    is_authorized=True,
                    status="approved",
                ),
                types.SimpleNamespace(
                    provider_name="vpn456",
                    provider_url=None,
                    is_authorized=False,
                    status="pending",
                ),
            ]
        )

        _patch_admin_client(monkeypatch, client)

        result = runner.invoke(admin_app, ["get-user-providers", "42"])

        assert result.exit_code == 0
        assert "vpn123" in result.stdout
        assert "vpn456" in result.stdout
        client.get_user_providers.assert_called_once_with(42)

    def test_no_connections_shows_message(
        self,
        monkeypatch: pytest.MonkeyPatch,
        admin_app: typer.Typer,
    ) -> None:
        client = MagicMock(spec=AdminClient)
        client.get_user_providers.return_value = types.SimpleNamespace(connections=[])

        _patch_admin_client(monkeypatch, client)

        result = runner.invoke(admin_app, ["get-user-providers", "42"])

        assert result.exit_code == 0
        assert "No provider connections found" in result.stdout

    def test_error_shown_on_failure(
        self,
        monkeypatch: pytest.MonkeyPatch,
        admin_app: typer.Typer,
    ) -> None:
        client = MagicMock(spec=AdminClient)
        client.get_user_providers.side_effect = VPNAPIError("not found")

        _patch_admin_client(monkeypatch, client)

        result = runner.invoke(admin_app, ["get-user-providers", "42"])

        assert result.exit_code == 1


class TestGetUserProviderCommand:
    def test_gets_single_connection(
        self,
        monkeypatch: pytest.MonkeyPatch,
        admin_app: typer.Typer,
    ) -> None:
        client = MagicMock(spec=AdminClient)
        client.get_user_provider.return_value = types.SimpleNamespace(
            provider_name="vpn123",
            provider_url="https://vpn123.example.com",
            is_authorized=True,
            status="approved",
        )

        _patch_admin_client(monkeypatch, client)

        result = runner.invoke(admin_app, ["get-user-provider", "42", "vpn123"])

        assert result.exit_code == 0
        assert "vpn123" in result.stdout
        assert "approved" in result.stdout
        client.get_user_provider.assert_called_once_with(42, "vpn123")

    def test_error_shown_on_failure(
        self,
        monkeypatch: pytest.MonkeyPatch,
        admin_app: typer.Typer,
    ) -> None:
        client = MagicMock(spec=AdminClient)
        client.get_user_provider.side_effect = VPNAPIError("not found")

        _patch_admin_client(monkeypatch, client)

        result = runner.invoke(admin_app, ["get-user-provider", "42", "vpn123"])

        assert result.exit_code == 1


class TestGetProviderAuthorizationCommand:
    def test_gets_authorization(
        self,
        monkeypatch: pytest.MonkeyPatch,
        admin_app: typer.Typer,
    ) -> None:
        client = MagicMock(spec=AdminClient)
        client.get_provider_authorization.return_value = types.SimpleNamespace(
            user_id=42,
            provider_name="vpn123",
            provider_url="https://vpn123.example.com",
            status="pending",
        )

        _patch_admin_client(monkeypatch, client)

        result = runner.invoke(admin_app, ["get-provider-authorization", "vpn123", "42"])

        assert result.exit_code == 0
        assert "pending" in result.stdout
        client.get_provider_authorization.assert_called_once_with(
            provider_name="vpn123", user_id=42
        )

    def test_error_shown_on_failure(
        self,
        monkeypatch: pytest.MonkeyPatch,
        admin_app: typer.Typer,
    ) -> None:
        client = MagicMock(spec=AdminClient)
        client.get_provider_authorization.side_effect = VPNAPIError("not found")

        _patch_admin_client(monkeypatch, client)

        result = runner.invoke(admin_app, ["get-provider-authorization", "vpn123", "42"])

        assert result.exit_code == 1


class TestProcessProviderAuthorizationCommand:
    def test_processes_without_hmac(
        self,
        monkeypatch: pytest.MonkeyPatch,
        admin_app: typer.Typer,
    ) -> None:
        client = MagicMock(spec=AdminClient)
        client.process_provider_authorization.return_value = types.SimpleNamespace(
            user_id=42,
            provider_name="vpn123",
            status="pending",
        )

        _patch_admin_client(monkeypatch, client)

        result = runner.invoke(admin_app, ["process-provider-authorization", "42", "vpn123"])

        assert result.exit_code == 0
        assert "pending" in result.stdout
        client.process_provider_authorization.assert_called_once_with(
            user_id=42, provider_name="vpn123", hmac=None
        )

    def test_processes_with_hmac(
        self,
        monkeypatch: pytest.MonkeyPatch,
        admin_app: typer.Typer,
    ) -> None:
        client = MagicMock(spec=AdminClient)
        client.process_provider_authorization.return_value = types.SimpleNamespace(
            user_id=42,
            provider_name="vpn123",
            status="pending",
        )

        _patch_admin_client(monkeypatch, client)

        result = runner.invoke(
            admin_app,
            ["process-provider-authorization", "42", "vpn123", "--hmac", "abc123"],
        )

        assert result.exit_code == 0
        client.process_provider_authorization.assert_called_once_with(
            user_id=42, provider_name="vpn123", hmac="abc123"
        )

    def test_error_shown_on_failure(
        self,
        monkeypatch: pytest.MonkeyPatch,
        admin_app: typer.Typer,
    ) -> None:
        client = MagicMock(spec=AdminClient)
        client.process_provider_authorization.side_effect = VPNAPIError("invalid hmac")

        _patch_admin_client(monkeypatch, client)

        result = runner.invoke(admin_app, ["process-provider-authorization", "42", "vpn123"])

        assert result.exit_code == 1


class TestApproveProviderAuthorizationCommand:
    def test_approves(
        self,
        monkeypatch: pytest.MonkeyPatch,
        admin_app: typer.Typer,
    ) -> None:
        client = MagicMock(spec=AdminClient)
        client.approve_provider_authorization.return_value = types.SimpleNamespace(
            user_id=42,
            provider_name="vpn123",
            status="approved",
        )

        _patch_admin_client(monkeypatch, client)

        result = runner.invoke(admin_app, ["approve-provider-authorization", "42", "vpn123"])

        assert result.exit_code == 0
        assert "approved" in result.stdout
        client.approve_provider_authorization.assert_called_once_with(
            user_id=42, provider_name="vpn123"
        )

    def test_error_shown_on_conflict(
        self,
        monkeypatch: pytest.MonkeyPatch,
        admin_app: typer.Typer,
    ) -> None:
        client = MagicMock(spec=AdminClient)
        client.approve_provider_authorization.side_effect = VPNAPIError("not pending")

        _patch_admin_client(monkeypatch, client)

        result = runner.invoke(admin_app, ["approve-provider-authorization", "42", "vpn123"])

        assert result.exit_code == 1


class TestRejectProviderAuthorizationCommand:
    def test_rejects_with_force(
        self,
        monkeypatch: pytest.MonkeyPatch,
        admin_app: typer.Typer,
    ) -> None:
        client = MagicMock(spec=AdminClient)
        client.reject_provider_authorization.return_value = types.SimpleNamespace(
            user_id=42,
            provider_name="vpn123",
            status=None,
        )

        _patch_admin_client(monkeypatch, client)

        result = runner.invoke(
            admin_app, ["reject-provider-authorization", "42", "vpn123", "--force"]
        )

        assert result.exit_code == 0
        assert "Deleted" in result.stdout
        client.reject_provider_authorization.assert_called_once_with(
            user_id=42, provider_name="vpn123"
        )

    def test_shows_revoked_outcome_when_subscriptions_exist(
        self,
        monkeypatch: pytest.MonkeyPatch,
        admin_app: typer.Typer,
    ) -> None:
        client = MagicMock(spec=AdminClient)
        client.reject_provider_authorization.return_value = types.SimpleNamespace(
            user_id=42,
            provider_name="vpn123",
            status="revoked",
        )

        _patch_admin_client(monkeypatch, client)

        result = runner.invoke(
            admin_app, ["reject-provider-authorization", "42", "vpn123", "--force"]
        )

        assert result.exit_code == 0
        assert "revoked" in result.stdout

    def test_prompts_for_confirmation_without_force(
        self,
        monkeypatch: pytest.MonkeyPatch,
        admin_app: typer.Typer,
    ) -> None:
        client = MagicMock(spec=AdminClient)
        _patch_admin_client(monkeypatch, client)

        result = runner.invoke(
            admin_app, ["reject-provider-authorization", "42", "vpn123"], input="n\n"
        )

        assert result.exit_code == 0
        assert "Cancelled" in result.stdout
        client.reject_provider_authorization.assert_not_called()

    def test_confirmed_prompt_rejects(
        self,
        monkeypatch: pytest.MonkeyPatch,
        admin_app: typer.Typer,
    ) -> None:
        client = MagicMock(spec=AdminClient)
        client.reject_provider_authorization.return_value = types.SimpleNamespace(
            user_id=42,
            provider_name="vpn123",
            status=None,
        )
        _patch_admin_client(monkeypatch, client)

        result = runner.invoke(
            admin_app, ["reject-provider-authorization", "42", "vpn123"], input="y\n"
        )

        assert result.exit_code == 0
        client.reject_provider_authorization.assert_called_once_with(
            user_id=42, provider_name="vpn123"
        )

    def test_error_shown_on_failure(
        self,
        monkeypatch: pytest.MonkeyPatch,
        admin_app: typer.Typer,
    ) -> None:
        client = MagicMock(spec=AdminClient)
        client.reject_provider_authorization.side_effect = VPNAPIError("not pending")

        _patch_admin_client(monkeypatch, client)

        result = runner.invoke(
            admin_app, ["reject-provider-authorization", "42", "vpn123", "--force"]
        )

        assert result.exit_code == 1


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
