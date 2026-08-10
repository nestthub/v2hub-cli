"""End-to-end style tests for v2hub_cli.cli commands, using typer's CliRunner.

The real network-facing client is replaced with a MagicMock via
monkeypatching `ClientManager.get_client`, so these tests exercise the
actual command wiring (argument parsing, output, exit codes) without any
network access.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from v2hub_cli import cli

if TYPE_CHECKING:
    from collections.abc import Iterator

runner = CliRunner()


def _patch_get_client(monkeypatch: pytest.MonkeyPatch, client: MagicMock) -> None:
    @contextmanager
    def fake_get_client(
        base_url: str | None = None, api_token: str | None = None
    ) -> Iterator[MagicMock]:
        yield client

    monkeypatch.setattr(cli.ClientManager, "get_client", fake_get_client)


def _patch_get_client_raises(monkeypatch: pytest.MonkeyPatch, exc: Exception) -> None:
    @contextmanager
    def fake_get_client(base_url: str | None = None, api_token: str | None = None) -> Iterator[Any]:
        raise exc
        yield  # pragma: no cover

    monkeypatch.setattr(cli.ClientManager, "get_client", fake_get_client)


class TestVersionCommand:
    def test_shows_versions(self) -> None:
        result = runner.invoke(cli.app, ["version"])
        assert result.exit_code == 0
        assert "Versions" in result.stdout


class TestListCommand:
    def test_lists_subscriptions(
        self, monkeypatch: pytest.MonkeyPatch, make_subscription: Any
    ) -> None:
        client = MagicMock()
        client.list_subscriptions.return_value = [make_subscription(name="sub-a")]
        _patch_get_client(monkeypatch, client)

        result = runner.invoke(cli.app, ["list"])
        assert result.exit_code == 0
        assert "sub-a" in result.stdout

    def test_no_subscriptions_shows_message(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = MagicMock()
        client.list_subscriptions.return_value = []
        _patch_get_client(monkeypatch, client)

        result = runner.invoke(cli.app, ["list"])
        assert result.exit_code == 0
        assert "No subscriptions found" in result.stdout

    def test_missing_config_exits_nonzero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_get_client_raises(monkeypatch, ValueError("API URL not provided"))

        result = runner.invoke(cli.app, ["list"])
        assert result.exit_code == 1
        assert "API URL not provided" in result.stdout

    def test_unexpected_exception_exits_nonzero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_get_client_raises(monkeypatch, RuntimeError("connection refused"))

        result = runner.invoke(cli.app, ["list"])
        assert result.exit_code == 1
        assert "connection refused" in result.stdout


class TestCreateCommand:
    def test_creates_subscription(
        self, monkeypatch: pytest.MonkeyPatch, make_subscription: Any
    ) -> None:
        client = MagicMock()
        client.create_subscription.return_value = make_subscription(
            name="new-sub", token="tok_new", sources_count=0
        )
        _patch_get_client(monkeypatch, client)

        result = runner.invoke(cli.app, ["create", "new-sub"])
        assert result.exit_code == 0
        assert "new-sub" in result.stdout
        assert "tok_new" in result.stdout
        client.create_subscription.assert_called_once()
        args = client.create_subscription.call_args.args
        assert args[0] == "new-sub"

    def test_creates_with_sources(
        self, monkeypatch: pytest.MonkeyPatch, make_subscription: Any
    ) -> None:
        client = MagicMock()
        client.create_subscription.return_value = make_subscription(name="new-sub")
        _patch_get_client(monkeypatch, client)

        result = runner.invoke(
            cli.app,
            ["create", "new-sub", "-s", "vless://a", "-s", "vless://b"],
        )
        assert result.exit_code == 0
        sources_arg = client.create_subscription.call_args.args[2]
        assert len(sources_arg) == 2

    def test_invalid_json_source_fails_gracefully(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = MagicMock()
        _patch_get_client(monkeypatch, client)

        result = runner.invoke(cli.app, ["create", "new-sub", "-s", "{bad json"])
        assert result.exit_code != 0


class TestGetCommand:
    def test_shows_subscription_detail(
        self, monkeypatch: pytest.MonkeyPatch, make_subscription: Any
    ) -> None:
        client = MagicMock()
        client.get_subscription.return_value = make_subscription(name="detail-sub")
        _patch_get_client(monkeypatch, client)

        result = runner.invoke(cli.app, ["get", "tok_123"])
        assert result.exit_code == 0
        assert "detail-sub" in result.stdout
        client.get_subscription.assert_called_once_with("tok_123", as_provider_for_user_id=None)


class TestAddSourcesCommand:
    def test_adds_sources(self, monkeypatch: pytest.MonkeyPatch, make_subscription: Any) -> None:
        client = MagicMock()
        client.add_sources.return_value = make_subscription(sources_count=5)
        _patch_get_client(monkeypatch, client)

        result = runner.invoke(cli.app, ["add-sources", "tok_123", "-s", "vless://x"])
        assert result.exit_code == 0
        assert "5" in result.stdout
        client.add_sources.assert_called_once()
        assert client.add_sources.call_args.args[0] == "tok_123"


class TestReplaceSourcesCommand:
    def test_replaces_sources(
        self, monkeypatch: pytest.MonkeyPatch, make_subscription: Any
    ) -> None:
        client = MagicMock()
        client.replace_sources.return_value = make_subscription(sources_count=1)
        _patch_get_client(monkeypatch, client)

        result = runner.invoke(cli.app, ["replace-sources", "tok_123", "-s", "vless://x"])
        assert result.exit_code == 0
        client.replace_sources.assert_called_once()


class TestRemoveSourcesCommand:
    def test_removes_with_force_skips_confirmation(
        self, monkeypatch: pytest.MonkeyPatch, make_subscription: Any
    ) -> None:
        client = MagicMock()
        client.remove_sources.return_value = make_subscription(sources_count=0)
        _patch_get_client(monkeypatch, client)

        result = runner.invoke(cli.app, ["remove-sources", "tok_123", "-s", "vless://x", "--force"])
        assert result.exit_code == 0
        client.remove_sources.assert_called_once_with(
            "tok_123", ["vless://x"], as_provider_for_user_id=None
        )

    def test_without_force_prompts_and_cancels_on_no(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = MagicMock()
        _patch_get_client(monkeypatch, client)

        result = runner.invoke(
            cli.app, ["remove-sources", "tok_123", "-s", "vless://x"], input="n\n"
        )
        assert result.exit_code == 0
        assert "Cancelled" in result.stdout
        client.remove_sources.assert_not_called()

    def test_without_force_confirms_on_yes(
        self, monkeypatch: pytest.MonkeyPatch, make_subscription: Any
    ) -> None:
        client = MagicMock()
        client.remove_sources.return_value = make_subscription(sources_count=0)
        _patch_get_client(monkeypatch, client)

        result = runner.invoke(
            cli.app, ["remove-sources", "tok_123", "-s", "vless://x"], input="y\n"
        )
        assert result.exit_code == 0
        client.remove_sources.assert_called_once()


class TestDeleteCommand:
    def test_deletes_with_force(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = MagicMock()
        _patch_get_client(monkeypatch, client)

        result = runner.invoke(cli.app, ["delete", "tok_123", "--force"])
        assert result.exit_code == 0
        client.delete_subscription.assert_called_once_with("tok_123", as_provider_for_user_id=None)

    def test_cancels_without_confirmation(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = MagicMock()
        _patch_get_client(monkeypatch, client)

        result = runner.invoke(cli.app, ["delete", "tok_123"], input="n\n")
        assert result.exit_code == 0
        assert "Cancelled" in result.stdout
        client.delete_subscription.assert_not_called()


class TestUpdateCommand:
    def test_no_fields_shows_warning_without_calling_client(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        client = MagicMock()
        _patch_get_client(monkeypatch, client)

        result = runner.invoke(cli.app, ["update", "tok_123"])
        assert result.exit_code == 0
        assert "Nothing to update" in result.stdout
        client.update_subscription.assert_not_called()

    def test_updates_name(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = MagicMock()
        _patch_get_client(monkeypatch, client)

        result = runner.invoke(cli.app, ["update", "tok_123", "--name", "renamed"])
        assert result.exit_code == 0
        assert "Subscription updated" in result.stdout
        client.update_subscription.assert_called_once_with(
            "tok_123", "renamed", None, as_provider_for_user_id=None
        )

    def test_updates_description(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = MagicMock()
        _patch_get_client(monkeypatch, client)

        result = runner.invoke(cli.app, ["update", "tok_123", "--description", "new desc"])
        assert result.exit_code == 0
        client.update_subscription.assert_called_once_with(
            "tok_123", None, "new desc", as_provider_for_user_id=None
        )


class TestUpdateConfigCommand:
    def test_no_fields_shows_warning(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = MagicMock()
        _patch_get_client(monkeypatch, client)

        result = runner.invoke(cli.app, ["update-config", "tok_123", "-i", "cfg1"])
        assert result.exit_code == 0
        assert "Nothing to update" in result.stdout
        client.update_source.assert_not_called()

    def test_updates_comment_only(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = MagicMock()
        _patch_get_client(monkeypatch, client)

        result = runner.invoke(
            cli.app, ["update-config", "tok_123", "-i", "cfg1", "-c", "new comment"]
        )
        assert result.exit_code == 0
        client.update_source.assert_called_once_with(
            "tok_123",
            "cfg1",
            comment="new comment",
            is_hidden=None,
            max_depth=None,
            as_provider_for_user_id=None,
        )

    def test_updates_hidden_flag(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = MagicMock()
        _patch_get_client(monkeypatch, client)

        result = runner.invoke(cli.app, ["update-config", "tok_123", "-i", "cfg1", "--hidden"])
        assert result.exit_code == 0
        client.update_source.assert_called_once_with(
            "tok_123",
            "cfg1",
            comment=None,
            is_hidden=True,
            max_depth=None,
            as_provider_for_user_id=None,
        )

    def test_updates_max_depth(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = MagicMock()
        _patch_get_client(monkeypatch, client)

        result = runner.invoke(
            cli.app, ["update-config", "tok_123", "-i", "cfg1", "--max-depth", "2"]
        )
        assert result.exit_code == 0
        client.update_source.assert_called_once_with(
            "tok_123",
            "cfg1",
            comment=None,
            is_hidden=None,
            max_depth=2,
            as_provider_for_user_id=None,
        )

    def test_max_depth_out_of_range_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = MagicMock()
        _patch_get_client(monkeypatch, client)

        result = runner.invoke(
            cli.app, ["update-config", "tok_123", "-i", "cfg1", "--max-depth", "10"]
        )
        assert result.exit_code != 0


class TestUpdateCommentDeprecatedCommand:
    def test_still_works_and_warns_deprecation(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = MagicMock()
        _patch_get_client(monkeypatch, client)

        result = runner.invoke(cli.app, ["update-comment", "tok_123", "-i", "cfg1", "-c", "hello"])
        assert result.exit_code == 0
        assert "deprecated" in result.stdout.lower()
        client.update_comment.assert_called_once_with(
            "tok_123", "cfg1", "hello", as_provider_for_user_id=None
        )


class TestRefreshCommand:
    def test_nothing_to_refresh(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = MagicMock()
        result_obj = MagicMock()
        result_obj.refreshed = 0
        result_obj.failed = 0
        result_obj.skipped = 0
        result_obj.total = 0
        result_obj.message = "Nothing to refresh"
        result_obj.errors = []
        client.refresh_subscription.return_value = result_obj
        _patch_get_client(monkeypatch, client)

        result = runner.invoke(cli.app, ["refresh", "tok_123"])
        assert result.exit_code == 0
        assert "No Action" in result.stdout

    def test_skipped_only(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = MagicMock()
        result_obj = MagicMock()
        result_obj.refreshed = 0
        result_obj.failed = 0
        result_obj.skipped = 3
        result_obj.total = 3
        result_obj.message = "Cooldown active"
        result_obj.errors = []
        client.refresh_subscription.return_value = result_obj
        _patch_get_client(monkeypatch, client)

        result = runner.invoke(cli.app, ["refresh", "tok_123"])
        assert result.exit_code == 0
        assert "Skipped" in result.stdout

    def test_successful_refresh(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = MagicMock()
        result_obj = MagicMock()
        result_obj.refreshed = 2
        result_obj.failed = 0
        result_obj.skipped = 1
        result_obj.total = 3
        result_obj.message = None
        result_obj.errors = []
        client.refresh_subscription.return_value = result_obj
        _patch_get_client(monkeypatch, client)

        result = runner.invoke(cli.app, ["refresh", "tok_123"])
        assert result.exit_code == 0
        assert "Refresh Complete" in result.stdout

    def test_full_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = MagicMock()
        result_obj = MagicMock()
        result_obj.refreshed = 0
        result_obj.failed = 2
        result_obj.skipped = 0
        result_obj.total = 2
        result_obj.message = None
        result_obj.errors = ["timeout", "dns error"]
        client.refresh_subscription.return_value = result_obj
        _patch_get_client(monkeypatch, client)

        result = runner.invoke(cli.app, ["refresh", "tok_123"])
        assert result.exit_code == 0
        assert "Refresh Failed" in result.stdout
        assert "timeout" in result.stdout
        assert "dns error" in result.stdout


class TestErrorHandlingAcrossCommands:
    @pytest.mark.parametrize(
        "args",
        [
            ["list"],
            ["get", "tok_123"],
            ["create", "name"],
            ["refresh", "tok_123"],
        ],
    )
    def test_value_error_shows_missing_config_message(
        self, monkeypatch: pytest.MonkeyPatch, args: list[str]
    ) -> None:
        _patch_get_client_raises(monkeypatch, ValueError("boom config"))
        result = runner.invoke(cli.app, args)
        assert result.exit_code == 1
        assert "boom config" in result.stdout
