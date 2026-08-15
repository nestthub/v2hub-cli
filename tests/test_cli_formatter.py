"""Tests for v2hub_cli.cli_formatter.OutputFormatter."""

from __future__ import annotations

import types

import pytest
from rich.console import Console

from v2hub_cli.cli_formatter import OutputFormatter


@pytest.fixture
def console() -> Console:
    # record_console=False, plain rendering, no ANSI color codes to simplify assertions
    return Console(record=True, width=200, force_terminal=False, no_color=True)


@pytest.fixture
def formatter(console: Console) -> OutputFormatter:
    return OutputFormatter(console)


def render(console: Console) -> str:
    return console.export_text()


class TestShort:
    def test_returns_original_when_within_limit(self, formatter: OutputFormatter) -> None:
        assert formatter.short("hello", 12) == "hello"

    def test_truncates_with_ellipsis_when_too_long(self, formatter: OutputFormatter) -> None:
        result = formatter.short("this-is-a-very-long-string", 12)
        assert result == "this-is-a…"
        assert len(result) == 10

    def test_boundary_exact_length_untouched(self, formatter: OutputFormatter) -> None:
        text = "exactlength1"
        assert len(text) == 12
        assert formatter.short(text, 12) == text

    def test_max_length_at_or_below_three_returns_unchanged(
        self, formatter: OutputFormatter
    ) -> None:
        assert formatter.short("hello world", 3) == "hello world"
        assert formatter.short("hello world", 0) == "hello world"
        assert formatter.short("hello world", -5) == "hello world"

    def test_empty_string(self, formatter: OutputFormatter) -> None:
        assert formatter.short("", 12) == ""


class TestSafeStr:
    def test_none_becomes_default_dash(self) -> None:
        assert OutputFormatter._safe_str(None) == "-"

    def test_none_with_custom_default(self) -> None:
        assert OutputFormatter._safe_str(None, default="N/A") == "N/A"

    def test_non_none_value_stringified(self) -> None:
        assert OutputFormatter._safe_str(42) == "42"
        assert OutputFormatter._safe_str(True) == "True"

    def test_falsy_but_not_none_is_preserved(self) -> None:
        # 0, "" and False are not None so they should NOT be replaced by the default
        assert OutputFormatter._safe_str(0) == "0"
        assert OutputFormatter._safe_str("") == ""
        assert OutputFormatter._safe_str(False) == "False"


class TestShowError:
    def test_generic_exception_shows_plain_error(
        self, formatter: OutputFormatter, console: Console
    ) -> None:
        formatter.show_error(ValueError("boom"))
        output = render(console)
        assert "Error: boom" in output

    def test_vpn_api_error_shows_panel_with_recovery_hint(
        self,
        formatter: OutputFormatter,
        console: Console,
        fake_vpn_api_error: type,
    ) -> None:
        error = fake_vpn_api_error(
            "Something failed",
            retry_after=60,
        )

        formatter.show_error(error)

        output = render(console)

        assert "Something failed" in output
        assert "Recovery hint" in output

    def test_vpn_api_error_without_hint_shows_default(
        self,
        formatter: OutputFormatter,
        console: Console,
        fake_vpn_api_error: type,
    ) -> None:
        error = fake_vpn_api_error("Oops")

        formatter.show_error(error)

        output = render(console)

        assert "Oops" in output
        assert "Contact API support if problem persists" in output


class TestShowMissingConfig:
    def test_shows_message(self, formatter: OutputFormatter, console: Console) -> None:
        formatter.show_missing_config("API URL not provided")
        output = render(console)
        assert "API URL not provided" in output


class TestShowSuccess:
    def test_shows_basic_message(self, formatter: OutputFormatter, console: Console) -> None:
        formatter.show_success("Operation completed")
        output = render(console)
        assert "Operation completed" in output
        assert "Success" in output

    def test_shows_details(self, formatter: OutputFormatter, console: Console) -> None:
        formatter.show_success(
            "Created",
            details={"Token": "abc123", "Sources": "3"},
        )
        output = render(console)
        assert "Token" in output
        assert "abc123" in output
        assert "Sources" in output
        assert "3" in output

    def test_custom_title(self, formatter: OutputFormatter, console: Console) -> None:
        formatter.show_success("Done", title="Custom Title")
        output = render(console)
        assert "Custom Title" in output


class TestCreateSubscriptionTable:
    def test_empty_list_produces_table_with_title(self, formatter: OutputFormatter) -> None:
        table = formatter.create_subscription_table([])
        assert table.title == "📋 Subscriptions"
        assert table.row_count == 0

    def test_populates_rows_from_subscriptions(
        self, formatter: OutputFormatter, make_subscription: object
    ) -> None:
        sub1 = make_subscription(name="sub-one", token="tok1", sources_count=5)
        sub2 = make_subscription(name="sub-two", token="tok2", sources_count=0)

        table = formatter.create_subscription_table([sub1, sub2])
        assert table.row_count == 2

    def test_missing_attributes_render_as_dash(self, formatter: OutputFormatter) -> None:
        bare = types.SimpleNamespace()  # no name/token/sources_count/description
        table = formatter.create_subscription_table([bare])
        assert table.row_count == 1

    def test_custom_title(self, formatter: OutputFormatter) -> None:
        table = formatter.create_subscription_table([], title="My Subs")
        assert table.title == "My Subs"


class TestShowVersion:
    def test_shows_all_versions(self, formatter: OutputFormatter, console: Console) -> None:
        formatter.show_version({"v2hub": "1.0.0", "v2hub-cli": "1.0.3", "v2hub-admin": "2.0.0"})
        output = render(console)
        assert "v2hub" in output
        assert "1.0.0" in output
        assert "v2hub-cli" in output
        assert "1.0.3" in output
        assert "v2hub-admin" in output
        assert "2.0.0" in output

    def test_empty_versions_still_renders_panel(
        self, formatter: OutputFormatter, console: Console
    ) -> None:
        formatter.show_version({})
        output = render(console)
        assert "Versions" in output


class TestShowSubscriptionDetail:
    def test_shows_basic_fields(
        self, formatter: OutputFormatter, console: Console, make_subscription: object
    ) -> None:
        sub = make_subscription(name="my-sub", token="tok_abc", sources_count=4)
        formatter.show_subscription_detail(sub)
        output = render(console)
        assert "my-sub" in output
        assert "tok_abc" in output
        assert "4" in output

    def test_no_sources_skips_sources_table(
        self, formatter: OutputFormatter, console: Console, make_subscription: object
    ) -> None:
        sub = make_subscription(sources=[])
        formatter.show_subscription_detail(sub)
        output = render(console)
        assert "Sources" not in output.split("📦 Subscription")[-1] or "📡 Sources" not in output

    def test_renders_sources_table_when_present(
        self, formatter: OutputFormatter, console: Console, make_subscription: object
    ) -> None:
        source = types.SimpleNamespace(
            id="src1",
            source_type="url",
            data="https://example.com/sub",
            is_hidden=False,
            max_depth=1,
            order_index=0,
        )
        sub = make_subscription(sources=[source])
        formatter.show_subscription_detail(sub)
        output = render(console)
        assert "📡 Sources" in output
        assert "src1" in output

    def test_config_source_type_truncates_comment(
        self, formatter: OutputFormatter, console: Console, make_subscription: object
    ) -> None:
        from v2hub.models import SourceType

        long_comment = "x" * 100
        source = types.SimpleNamespace(
            id="src2",
            source_type=SourceType.CONFIG,
            data=f"vless://uuid@host:443?params#{long_comment}",
            is_hidden=True,
            max_depth=0,
            order_index=1,
        )
        sub = make_subscription(sources=[source])
        formatter.show_subscription_detail(sub)
        output = render(console)
        assert "src2" in output
        # comment should have been shortened, so the full 100-char comment
        # must not appear verbatim
        assert long_comment not in output

    def test_hidden_source_shows_cross_mark(
        self, formatter: OutputFormatter, console: Console, make_subscription: object
    ) -> None:
        source = types.SimpleNamespace(
            id="src3",
            source_type="url",
            data="https://example.com",
            is_hidden=True,
            max_depth=None,
            order_index=None,
        )
        sub = make_subscription(sources=[source])
        formatter.show_subscription_detail(sub)
        output = render(console)
        assert "✗" in output

    def test_visible_source_shows_check_mark(
        self, formatter: OutputFormatter, console: Console, make_subscription: object
    ) -> None:
        source = types.SimpleNamespace(
            id="src4",
            source_type="url",
            data="https://example.com",
            is_hidden=False,
            max_depth=None,
            order_index=None,
        )
        sub = make_subscription(sources=[source])
        formatter.show_subscription_detail(sub)
        output = render(console)
        assert "✓" in output
