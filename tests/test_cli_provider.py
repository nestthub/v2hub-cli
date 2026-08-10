"""End-to-end style tests for v2hub_cli's `provider {user_id} ...` command group.

Same approach as test_cli.py: the real network-facing client is replaced
with a MagicMock via monkeypatching `ClientManager.get_client`, so these
tests exercise the actual command wiring (argument parsing, output, exit
codes, and the exact arguments forwarded to the v2hub client) without any
network access.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

from typer.testing import CliRunner

from v2hub_cli import cli

if TYPE_CHECKING:
    from collections.abc import Iterator

    import pytest

runner = CliRunner()


def _patch_get_client(
    monkeypatch: pytest.MonkeyPatch, client: MagicMock, calls: list[tuple[Any, Any]] | None = None
) -> None:
    """
    Same as test_cli.py's _patch_get_client, but optionally records the
    (base_url, api_token) pair ClientManager.get_client was invoked with,
    so provider-authentication tests can assert on it directly.
    """

    @contextmanager
    def fake_get_client(
        base_url: str | None = None, api_token: str | None = None
    ) -> Iterator[MagicMock]:
        if calls is not None:
            calls.append((base_url, api_token))
        yield client

    monkeypatch.setattr(cli.ClientManager, "get_client", fake_get_client)


def _patch_get_client_raises(monkeypatch: pytest.MonkeyPatch, exc: Exception) -> None:
    @contextmanager
    def fake_get_client(base_url: str | None = None, api_token: str | None = None) -> Iterator[Any]:
        raise exc
        yield  # pragma: no cover

    monkeypatch.setattr(cli.ClientManager, "get_client", fake_get_client)


# ═══════════════════════════════════════════════════════════════════════════
# Command group presence / user_id argument
# ═══════════════════════════════════════════════════════════════════════════


class TestProviderCommandGroup:
    def test_provider_group_is_registered(self) -> None:
        result = runner.invoke(cli.app, ["--help"])
        assert result.exit_code == 0
        assert "provider" in result.stdout

    def test_provider_requires_user_id(self) -> None:
        result = runner.invoke(cli.app, ["provider"])
        assert result.exit_code != 0

    def test_provider_user_id_must_be_numeric(self) -> None:
        result = runner.invoke(cli.app, ["provider", "not-a-number", "list"])
        assert result.exit_code != 0

    def test_provider_help_lists_subscription_and_connection_commands(self) -> None:
        result = runner.invoke(cli.app, ["provider", "123", "--help"])
        assert result.exit_code == 0
        for cmd in [
            "list",
            "create",
            "get",
            "add-sources",
            "replace-sources",
            "remove-sources",
            "delete",
            "update",
            "update-config",
            "refresh",
            "connection-get",
            "connection-create",
            "connection-revoke",
            "connection-delete",
        ]:
            assert cmd in result.stdout


# ═══════════════════════════════════════════════════════════════════════════
# user_id propagation into the client
# ═══════════════════════════════════════════════════════════════════════════


class TestProviderUserIdPropagation:
    def test_list_forwards_user_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = MagicMock()
        client.list_subscriptions.return_value = []
        _patch_get_client(monkeypatch, client)

        result = runner.invoke(cli.app, ["provider", "555", "list"])
        assert result.exit_code == 0
        client.list_subscriptions.assert_called_once_with(as_provider_for_user_id=555)

    def test_create_forwards_user_id(
        self, monkeypatch: pytest.MonkeyPatch, make_subscription: Any
    ) -> None:
        client = MagicMock()
        client.create_subscription.return_value = make_subscription(name="new-sub")
        _patch_get_client(monkeypatch, client)

        result = runner.invoke(cli.app, ["provider", "555", "create", "new-sub"])
        assert result.exit_code == 0
        client.create_subscription.assert_called_once_with(
            "new-sub", None, [], as_provider_for_user_id=555
        )

    def test_get_forwards_user_id(
        self, monkeypatch: pytest.MonkeyPatch, make_subscription: Any
    ) -> None:
        client = MagicMock()
        client.get_subscription.return_value = make_subscription()
        _patch_get_client(monkeypatch, client)

        result = runner.invoke(cli.app, ["provider", "555", "get", "tok_123"])
        assert result.exit_code == 0
        client.get_subscription.assert_called_once_with("tok_123", as_provider_for_user_id=555)

    def test_add_sources_forwards_user_id(
        self, monkeypatch: pytest.MonkeyPatch, make_subscription: Any
    ) -> None:
        client = MagicMock()
        client.add_sources.return_value = make_subscription()
        _patch_get_client(monkeypatch, client)

        result = runner.invoke(
            cli.app, ["provider", "555", "add-sources", "tok_123", "-s", "vless://a"]
        )
        assert result.exit_code == 0
        assert client.add_sources.call_args.kwargs["as_provider_for_user_id"] == 555

    def test_replace_sources_forwards_user_id(
        self, monkeypatch: pytest.MonkeyPatch, make_subscription: Any
    ) -> None:
        client = MagicMock()
        client.replace_sources.return_value = make_subscription()
        _patch_get_client(monkeypatch, client)

        result = runner.invoke(
            cli.app, ["provider", "555", "replace-sources", "tok_123", "-s", "vless://a"]
        )
        assert result.exit_code == 0
        assert client.replace_sources.call_args.kwargs["as_provider_for_user_id"] == 555

    def test_remove_sources_forwards_user_id(
        self, monkeypatch: pytest.MonkeyPatch, make_subscription: Any
    ) -> None:
        client = MagicMock()
        client.remove_sources.return_value = make_subscription()
        _patch_get_client(monkeypatch, client)

        result = runner.invoke(
            cli.app,
            ["provider", "555", "remove-sources", "tok_123", "-s", "vless://a", "--force"],
        )
        assert result.exit_code == 0
        assert client.remove_sources.call_args.kwargs["as_provider_for_user_id"] == 555

    def test_delete_forwards_user_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = MagicMock()
        _patch_get_client(monkeypatch, client)

        result = runner.invoke(cli.app, ["provider", "555", "delete", "tok_123", "--force"])
        assert result.exit_code == 0
        client.delete_subscription.assert_called_once_with("tok_123", as_provider_for_user_id=555)

    def test_update_forwards_user_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = MagicMock()
        _patch_get_client(monkeypatch, client)

        result = runner.invoke(cli.app, ["provider", "555", "update", "tok_123", "-n", "renamed"])
        assert result.exit_code == 0
        client.update_subscription.assert_called_once_with(
            "tok_123", "renamed", None, as_provider_for_user_id=555
        )

    def test_update_config_forwards_user_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = MagicMock()
        _patch_get_client(monkeypatch, client)

        result = runner.invoke(
            cli.app,
            ["provider", "555", "update-config", "tok_123", "-i", "cfg1", "-c", "hi"],
        )
        assert result.exit_code == 0
        client.update_source.assert_called_once_with(
            "tok_123",
            "cfg1",
            comment="hi",
            is_hidden=None,
            max_depth=None,
            as_provider_for_user_id=555,
        )

    def test_refresh_forwards_user_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = MagicMock()
        result_obj = MagicMock(refreshed=1, failed=0, skipped=0, total=1, message=None, errors=[])
        client.refresh_subscription.return_value = result_obj
        _patch_get_client(monkeypatch, client)

        result = runner.invoke(cli.app, ["provider", "555", "refresh", "tok_123"])
        assert result.exit_code == 0
        client.refresh_subscription.assert_called_once_with("tok_123", as_provider_for_user_id=555)

    def test_different_user_ids_produce_different_calls(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        client = MagicMock()
        client.list_subscriptions.return_value = []
        _patch_get_client(monkeypatch, client)

        runner.invoke(cli.app, ["provider", "111", "list"])
        runner.invoke(cli.app, ["provider", "222", "list"])

        calls = client.list_subscriptions.call_args_list
        assert calls[0].kwargs["as_provider_for_user_id"] == 111
        assert calls[1].kwargs["as_provider_for_user_id"] == 222


# ═══════════════════════════════════════════════════════════════════════════
# Provider authentication
# ═══════════════════════════════════════════════════════════════════════════
#
# The CLI does not implement provider auth itself -- it just forwards
# whatever --api-token / V2HUB_API_TOKEN resolves to into
# ClientManager.get_client(), exactly like it does for regular users.
# These tests confirm that forwarding happens unchanged for provider
# commands, rather than the CLI doing anything provider-specific with
# the token.


class TestProviderAuthentication:
    def test_provider_command_forwards_api_token_and_base_url(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        client = MagicMock()
        client.list_subscriptions.return_value = []
        calls: list[tuple[Any, Any]] = []
        _patch_get_client(monkeypatch, client, calls)

        result = runner.invoke(
            cli.app,
            [
                "provider",
                "555",
                "list",
                "--base-url",
                "https://api.example.com",
                "--api-token",
                "provider-token-abc",
            ],
        )
        assert result.exit_code == 0
        assert calls == [("https://api.example.com", "provider-token-abc")]

    def test_provider_command_uses_same_get_client_as_regular_commands(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        No separate "provider client" code path exists: provider commands
        call the exact same ClientManager.get_client() regular commands
        use. This is what "provider auth handled by v2hub, not the CLI"
        actually means in code -- there is nothing else to patch.
        """
        client = MagicMock()
        client.list_subscriptions.return_value = []
        calls: list[tuple[Any, Any]] = []
        _patch_get_client(monkeypatch, client, calls)

        runner.invoke(cli.app, ["list", "--api-token", "user-token"])
        runner.invoke(cli.app, ["provider", "555", "list", "--api-token", "provider-token"])

        assert calls == [
            (None, "user-token"),
            (None, "provider-token"),
        ]

    def test_provider_command_missing_config_reports_same_as_regular(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _patch_get_client_raises(monkeypatch, ValueError("API token not provided"))

        result = runner.invoke(cli.app, ["provider", "555", "list"])
        assert result.exit_code == 1
        assert "API token not provided" in result.stdout

    def test_provider_command_env_var_token_used(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Provider commands don't bypass the normal env-var resolution --
        V2HUB_API_TOKEN works the same way it does for regular commands.
        """
        monkeypatch.setenv("V2HUB_API_URL", "https://api.example.com")
        monkeypatch.setenv("V2HUB_API_TOKEN", "env-provider-token")

        captured: dict[str, Any] = {}

        class FakeClient:
            def __enter__(self) -> FakeClient:
                return self

            def __exit__(self, *exc: Any) -> None:
                return None

            def list_subscriptions(
                self, *, as_provider_for_user_id: int | None = None
            ) -> list[Any]:
                captured["as_provider_for_user_id"] = as_provider_for_user_id
                return []

        def fake_vpn_client(base_url: str, api_token: str) -> FakeClient:
            captured["base_url"] = base_url
            captured["api_token"] = api_token
            return FakeClient()

        monkeypatch.setattr("v2hub.client.VPNClient", fake_vpn_client)

        result = runner.invoke(cli.app, ["provider", "42", "list"])
        assert result.exit_code == 0
        assert captured["base_url"] == "https://api.example.com"
        assert captured["api_token"] == "env-provider-token"
        assert captured["as_provider_for_user_id"] == 42


# ═══════════════════════════════════════════════════════════════════════════
# Connection lifecycle
# ═══════════════════════════════════════════════════════════════════════════


class TestProviderConnectionGet:
    def test_shows_status(
        self, monkeypatch: pytest.MonkeyPatch, make_provider_connection: Any
    ) -> None:
        client = MagicMock()
        client.get_provider_connection.return_value = make_provider_connection(
            user_id=555, status="approved"
        )
        _patch_get_client(monkeypatch, client)

        result = runner.invoke(cli.app, ["provider", "555", "connection-get"])
        assert result.exit_code == 0
        assert "approved" in result.stdout.lower()
        client.get_provider_connection.assert_called_once_with(555)

    def test_missing_config_exits_nonzero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_get_client_raises(monkeypatch, ValueError("API token not provided"))

        result = runner.invoke(cli.app, ["provider", "555", "connection-get"])
        assert result.exit_code == 1

    def test_error_shown_on_failure(
        self, monkeypatch: pytest.MonkeyPatch, fake_vpn_api_error: type[Exception]
    ) -> None:
        client = MagicMock()
        client.get_provider_connection.side_effect = fake_vpn_api_error("not found")
        _patch_get_client(monkeypatch, client)

        result = runner.invoke(cli.app, ["provider", "555", "connection-get"])
        assert result.exit_code == 1


class TestProviderConnectionCreate:
    def test_creates_connection(
        self, monkeypatch: pytest.MonkeyPatch, make_provider_connection: Any
    ) -> None:
        client = MagicMock()
        client.create_provider_connection.return_value = make_provider_connection(
            user_id=555, status="approved"
        )
        _patch_get_client(monkeypatch, client)

        result = runner.invoke(cli.app, ["provider", "555", "connection-create"])
        assert result.exit_code == 0
        assert "approved" in result.stdout.lower()
        client.create_provider_connection.assert_called_once_with(555)

    def test_forwards_correct_user_id(
        self, monkeypatch: pytest.MonkeyPatch, make_provider_connection: Any
    ) -> None:
        client = MagicMock()
        client.create_provider_connection.return_value = make_provider_connection(user_id=999)
        _patch_get_client(monkeypatch, client)

        runner.invoke(cli.app, ["provider", "999", "connection-create"])
        client.create_provider_connection.assert_called_once_with(999)


class TestProviderConnectionRevoke:
    def test_revokes_with_force(
        self, monkeypatch: pytest.MonkeyPatch, make_provider_connection: Any
    ) -> None:
        client = MagicMock()
        client.revoke_provider_connection.return_value = make_provider_connection(
            user_id=555, status="revoked"
        )
        _patch_get_client(monkeypatch, client)

        result = runner.invoke(cli.app, ["provider", "555", "connection-revoke", "--force"])
        assert result.exit_code == 0
        assert "revoked" in result.stdout.lower()
        client.revoke_provider_connection.assert_called_once_with(555)

    def test_prompts_for_confirmation_without_force(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = MagicMock()
        _patch_get_client(monkeypatch, client)

        result = runner.invoke(cli.app, ["provider", "555", "connection-revoke"], input="n\n")
        assert result.exit_code == 0
        assert "Cancelled" in result.stdout
        client.revoke_provider_connection.assert_not_called()

    def test_confirmed_prompt_revokes(
        self, monkeypatch: pytest.MonkeyPatch, make_provider_connection: Any
    ) -> None:
        client = MagicMock()
        client.revoke_provider_connection.return_value = make_provider_connection(status="revoked")
        _patch_get_client(monkeypatch, client)

        result = runner.invoke(cli.app, ["provider", "555", "connection-revoke"], input="y\n")
        assert result.exit_code == 0
        client.revoke_provider_connection.assert_called_once_with(555)


class TestProviderConnectionDelete:
    def test_deletes_with_force(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = MagicMock()
        client.delete_provider_connection.return_value = MagicMock(
            detail="Provider connection deleted"
        )
        _patch_get_client(monkeypatch, client)

        result = runner.invoke(cli.app, ["provider", "555", "connection-delete", "--force"])
        assert result.exit_code == 0
        assert "deleted" in result.stdout.lower()
        client.delete_provider_connection.assert_called_once_with(555)

    def test_prompts_for_confirmation_without_force(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = MagicMock()
        _patch_get_client(monkeypatch, client)

        result = runner.invoke(cli.app, ["provider", "555", "connection-delete"], input="n\n")
        assert result.exit_code == 0
        assert "Cancelled" in result.stdout
        client.delete_provider_connection.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════════
# provider_name output / handling
# ═══════════════════════════════════════════════════════════════════════════


class TestProviderNameOutput:
    def test_list_shows_provider_column_when_present(
        self, monkeypatch: pytest.MonkeyPatch, make_subscription: Any
    ) -> None:
        client = MagicMock()
        client.list_subscriptions.return_value = [
            make_subscription(name="customer-sub", provider_name="Acme VPN Co")
        ]
        _patch_get_client(monkeypatch, client)

        result = runner.invoke(cli.app, ["provider", "555", "list"])
        assert result.exit_code == 0
        assert "Acme VPN Co" in result.stdout

    def test_list_hides_provider_column_for_regular_subscriptions(
        self, monkeypatch: pytest.MonkeyPatch, make_subscription: Any
    ) -> None:
        """
        Regression: regular user subscriptions (provider_name=None) must
        not show a "Provider" column or any provider-related text -- the
        existing self-service `list` output stays exactly as before.
        """
        client = MagicMock()
        client.list_subscriptions.return_value = [make_subscription(name="my-own-sub")]
        _patch_get_client(monkeypatch, client)

        result = runner.invoke(cli.app, ["list"])
        assert result.exit_code == 0
        assert "my-own-sub" in result.stdout
        assert "Provider" not in result.stdout

    def test_get_detail_shows_provider_name_when_present(
        self, monkeypatch: pytest.MonkeyPatch, make_subscription: Any
    ) -> None:
        client = MagicMock()
        client.get_subscription.return_value = make_subscription(
            name="customer-sub", provider_name="Acme VPN Co"
        )
        _patch_get_client(monkeypatch, client)

        result = runner.invoke(cli.app, ["provider", "555", "get", "tok_123"])
        assert result.exit_code == 0
        assert "Acme VPN Co" in result.stdout

    def test_get_detail_omits_provider_line_for_regular_subscription(
        self, monkeypatch: pytest.MonkeyPatch, make_subscription: Any
    ) -> None:
        """Regression: self-service `get` output is unaffected when provider_name is None."""
        client = MagicMock()
        client.get_subscription.return_value = make_subscription(
            name="my-own-sub", provider_name=None
        )
        _patch_get_client(monkeypatch, client)

        result = runner.invoke(cli.app, ["get", "tok_123"])
        assert result.exit_code == 0
        assert "my-own-sub" in result.stdout
        assert "Provider:" not in result.stdout


# ═══════════════════════════════════════════════════════════════════════════
# Regression: existing regular-user commands unaffected
# ═══════════════════════════════════════════════════════════════════════════


class TestRegularUserCommandsUnaffectedByProviderSupport:
    def test_list_does_not_pass_provider_kwarg_visibly_different(
        self, monkeypatch: pytest.MonkeyPatch, make_subscription: Any
    ) -> None:
        client = MagicMock()
        client.list_subscriptions.return_value = [make_subscription(name="sub-a")]
        _patch_get_client(monkeypatch, client)

        result = runner.invoke(cli.app, ["list"])
        assert result.exit_code == 0
        assert "sub-a" in result.stdout
        client.list_subscriptions.assert_called_once_with(as_provider_for_user_id=None)

    def test_create_self_service_uses_none_user_id(
        self, monkeypatch: pytest.MonkeyPatch, make_subscription: Any
    ) -> None:
        client = MagicMock()
        client.create_subscription.return_value = make_subscription(name="sub-a")
        _patch_get_client(monkeypatch, client)

        result = runner.invoke(cli.app, ["create", "sub-a"])
        assert result.exit_code == 0
        client.create_subscription.assert_called_once_with(
            "sub-a", None, [], as_provider_for_user_id=None
        )

    def test_no_provider_command_leaks_into_self_service_namespace(self) -> None:
        """`connection-get` etc. must not exist as top-level commands."""
        result = runner.invoke(cli.app, ["connection-get", "--help"])
        assert result.exit_code != 0


class TestVersionAndAdminUnaffectedByProvider:
    def test_version_command_still_works(self) -> None:
        result = runner.invoke(cli.app, ["version"])
        assert result.exit_code == 0
        assert "Versions" in result.stdout

    def test_version_command_not_nested_under_provider(self) -> None:
        result = runner.invoke(cli.app, ["provider", "555", "version"])
        assert result.exit_code != 0

    def test_admin_command_not_nested_under_provider(self) -> None:
        result = runner.invoke(cli.app, ["provider", "555", "admin"])
        assert result.exit_code != 0

    def test_top_level_admin_group_exists_or_absent_independent_of_provider(self) -> None:
        """
        Whether `admin` is registered depends only on v2hub-admin being
        installed -- provider support must not change that. We only
        assert this doesn't crash the top-level --help.
        """
        result = runner.invoke(cli.app, ["--help"])
        assert result.exit_code == 0
