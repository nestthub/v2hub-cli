"""
Unified CLI for VPN Subscription API.

Beautiful command-line interface with both regular and admin functionality.
"""

from __future__ import annotations

import json
from importlib.metadata import PackageNotFoundError, version
from typing import TYPE_CHECKING, Any

import typer
from rich.console import Console
from rich.panel import Panel

from v2hub.models import SourceCreate
from v2hub_cli import __version__ as cli_version
from v2hub_cli.cli_completion import (
    complete_config_hash,
    complete_provider_subscription_token,
    complete_subscription_token,
)
from v2hub_cli.cli_formatter import OutputFormatter
from v2hub_cli.cli_manager import ClientManager

if TYPE_CHECKING:
    from v2hub.client import VPNClient

app = typer.Typer(
    name="v2hub",
    help="VPN Subscription API Client CLI",
    add_completion=True,
)

console = Console()
formatter = OutputFormatter(console)


def _package_version(package: str) -> str:
    try:
        return version(package)
    except PackageNotFoundError:
        return "not installed"


def _get_versions() -> dict[str, str]:
    return {
        "v2hub": _package_version("v2hub"),
        "v2hub-cli": cli_version,
        "v2hub-admin": _package_version("v2hub-admin"),
    }


def _try_register_admin(app: typer.Typer) -> None:
    """
    Optional admin module registration.

    Admin CLI is treated as an optional plugin:
    - missing dependency → silently disabled
    - import/runtime error → logged, but CLI still works

    Deliberately independent of provider support: admin commands are
    excluded from the provider context and always operate against the
    admin secret-key auth mechanism, never a provider/user API token.
    """

    try:
        from v2hub_cli._admin_cli import register_admin_commands
    except ImportError:
        # optional feature not installed
        return

    admin_app = typer.Typer(
        name="admin",
        help="Admin API commands",
    )

    try:
        admin_commands = register_admin_commands(admin_app)
    except Exception as exc:
        console.print(
            "[yellow]Warning:[/yellow] admin CLI failed to initialize "
            f"and will be disabled. Reason: {exc}"
        )
        return

    app.add_typer(admin_app, name="admin", hidden=not admin_commands)


_try_register_admin(app)
# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _parse_source(raw: str) -> dict[str, Any]:
    """
    Parse a single --source value.

    Accepts either a plain string (source data, unchanged from the
    original calling convention):

        -s "http://127.0.0.1/sub/HC8pO7hca2QXcjtF6aTZOt9uI8v79I8R_gXXDp5_U3A"

    ...or a JSON object when you need per-source is_hidden/max_depth:

        -s '{"data": "http://127.0.0.1/sub/...", "hidden": true, "depth": 0}'

    Detected by whether the value starts with "{" after stripping
    whitespace, so ordinary source strings (vless://, vmess://, https://,
    etc.) are never mistaken for JSON. "hidden" defaults to false and
    "depth" is optional; only "data" is required inside the object.
    """
    stripped = raw.strip()
    if not stripped.startswith("{"):
        return {"data": stripped}

    try:
        obj = json.loads(stripped)
    except json.JSONDecodeError as e:
        raise typer.BadParameter(
            f"--source looks like JSON (starts with '{{') but failed to parse: {e}"
        ) from e

    if not isinstance(obj, dict) or "data" not in obj:
        raise typer.BadParameter(
            '--source JSON object must be an object with a "data" field, '
            'e.g. \'{"data": "vless://...", "hidden": true, "depth": 0}\''
        )

    entry: dict[str, Any] = {"data": obj["data"]}
    if obj.get("hidden"):
        entry["is_hidden"] = True
    if "depth" in obj and obj["depth"] is not None:
        entry["max_depth"] = obj["depth"]
    return entry


def _build_sources(sources: list[str]) -> list[SourceCreate]:
    """
    Build the sources payload sent to v2hub-core.

    Each item in `sources` is parsed independently via _parse_source(), so
    a single --source list can freely mix plain strings and JSON objects
    with per-source is_hidden/max_depth. Sources with no modifiers are
    sent as plain strings, identical to the pre-update calling convention
    -- nothing changes for existing scripts that don't use JSON sources.
    """
    return [SourceCreate(**_parse_source(s)) for s in sources]


# ═══════════════════════════════════════════════════════════════════════════
# Version Command
# ═══════════════════════════════════════════════════════════════════════════


@app.command(name="version")
def show_version() -> None:
    """Show version information."""
    formatter.show_version(_get_versions())


# ═══════════════════════════════════════════════════════════════════════════
# Shared command bodies
# ═══════════════════════════════════════════════════════════════════════════
#
# Every subscription/source operation lives here exactly once, as a plain
# function that takes an already-constructed `client` plus an optional
# `as_provider_for_user_id`. Both the top-level commands (regular
# self-service) and the `provider {user_id} ...` commands below call the
# *same* function -- they only differ in how they obtain `client` and
# whether they pass a user_id through. This is what keeps provider support
# from duplicating any request/formatting logic: nothing here talks HTTP
# directly, it only calls methods on the v2hub `VPNClient`, which already
# knows how to route self-service vs. provider calls and how to handle
# provider authentication.


def _do_list(client: VPNClient, *, as_provider_for_user_id: int | None = None) -> None:
    subs = client.list_subscriptions(as_provider_for_user_id=as_provider_for_user_id)

    if not subs:
        console.print("[yellow]No subscriptions found[/yellow]")
        return

    table = formatter.create_subscription_table(subs)
    console.print(table)


def _do_create(
    client: VPNClient,
    name: str,
    description: str | None,
    sources: list[str],
    *,
    as_provider_for_user_id: int | None = None,
) -> None:
    sub = client.create_subscription(
        name,
        description,
        _build_sources(sources),
        as_provider_for_user_id=as_provider_for_user_id,
    )

    formatter.show_success(
        f"Created subscription: [cyan]{sub.name}[/cyan]",
        details={
            "Token": f"[green]{sub.token}[/green]",
            "Sources": f"[yellow]{sub.sources_count}[/yellow]",
        },
    )


def _do_get(client: VPNClient, token: str, *, as_provider_for_user_id: int | None = None) -> None:
    sub = client.get_subscription(token, as_provider_for_user_id=as_provider_for_user_id)
    formatter.show_subscription_detail(sub)


def _do_add_sources(
    client: VPNClient,
    token: str,
    sources: list[str],
    *,
    as_provider_for_user_id: int | None = None,
) -> None:
    sub = client.add_sources(
        token, _build_sources(sources), as_provider_for_user_id=as_provider_for_user_id
    )

    formatter.show_success(
        f"Added [bold]{len(sources)}[/bold] source(s)",
        title="✅ Sources Updated",
        details={
            "Total configs": f"[yellow]{sub.sources_count}[/yellow]",
        },
    )


def _do_replace_sources(
    client: VPNClient,
    token: str,
    sources: list[str],
    *,
    as_provider_for_user_id: int | None = None,
) -> None:
    sub = client.replace_sources(
        token, _build_sources(sources), as_provider_for_user_id=as_provider_for_user_id
    )

    formatter.show_success(
        "Sources replaced",
        title="✅ Sources Replaced",
        details={
            "Total configs": f"[yellow]{sub.sources_count}[/yellow]",
        },
    )


def _do_remove_sources(
    client: VPNClient,
    token: str,
    sources: list[str],
    force: bool,
    *,
    as_provider_for_user_id: int | None = None,
) -> None:
    if not force:
        source_list = ", ".join(sources)
        confirm = typer.confirm(
            f"Remove sources [blue]{source_list}[/blue] from subscription [cyan]{token}[/cyan]?"
        )
        if not confirm:
            console.print("[yellow]Cancelled[/yellow]")
            return

    sub = client.remove_sources(token, sources, as_provider_for_user_id=as_provider_for_user_id)

    formatter.show_success(
        f"Removed [bold]{len(sources)}[/bold] source(s)",
        title="✅ Sources Updated",
        details={
            "Total configs": f"[yellow]{sub.sources_count}[/yellow]",
        },
    )


def _do_delete(
    client: VPNClient, token: str, force: bool, *, as_provider_for_user_id: int | None = None
) -> None:
    if not force:
        confirm = typer.confirm(f"Delete subscription {token}?")
        if not confirm:
            console.print("[yellow]Cancelled[/yellow]")
            return

    client.delete_subscription(token, as_provider_for_user_id=as_provider_for_user_id)
    formatter.show_success(f"Deleted subscription: [cyan]{token}[/cyan]")


def _do_update(
    client: VPNClient,
    token: str,
    name: str | None,
    description: str | None,
    *,
    as_provider_for_user_id: int | None = None,
) -> None:
    if not name and not description:
        console.print(
            Panel(
                "[yellow]No updates provided[/yellow]\n\n"
                "You must specify at least one option:\n"
                "  • --name\n"
                "  • --description",
                title="⚠️ Nothing to update",
                border_style="yellow",
            )
        )
        return

    client.update_subscription(
        token, name, description, as_provider_for_user_id=as_provider_for_user_id
    )

    updated_fields = []
    if name:
        updated_fields.append(f"name → [cyan]{name}[/cyan]")
    if description:
        updated_fields.append("description updated")

    console.print(
        Panel(
            "[green]✓[/green] Subscription updated\n\n"
            + "\n".join(f"  • {f}" for f in updated_fields),
            title="Success",
            border_style="green",
        )
    )


def _do_update_config(
    client: VPNClient,
    token: str,
    config_id: str,
    comment: str | None,
    hidden: bool | None,
    max_depth: int | None,
    *,
    as_provider_for_user_id: int | None = None,
) -> None:
    if comment is None and hidden is None and max_depth is None:
        console.print(
            Panel(
                "[yellow]No updates provided[/yellow]\n\n"
                "You must specify at least one option:\n"
                "  • --comment\n"
                "  • --hidden / --visible\n"
                "  • --max-depth",
                title="⚠️ Nothing to update",
                border_style="yellow",
            )
        )
        return

    client.update_source(
        token,
        config_id,
        comment=comment,
        is_hidden=hidden,
        max_depth=max_depth,
        as_provider_for_user_id=as_provider_for_user_id,
    )

    details = {"Config": formatter.short(config_id, 20)}
    if comment is not None:
        details["Comment"] = comment
    if hidden is not None:
        details["Hidden"] = str(hidden)
    if max_depth is not None:
        details["Max depth"] = str(max_depth)

    formatter.show_success(
        "Config updated successfully",
        title="Updated",
        details=details,
    )


def _do_update_comment(
    client: VPNClient,
    token: str,
    config_id: str,
    comment: str,
    *,
    as_provider_for_user_id: int | None = None,
) -> None:
    console.print(
        "[yellow]⚠ 'update-comment' is deprecated and will not receive "
        "further updates. Use 'update-config' instead.[/yellow]"
    )
    client.update_comment(
        token, config_id, comment, as_provider_for_user_id=as_provider_for_user_id
    )

    formatter.show_success(
        "Comment updated successfully",
        title="Updated",
        details={
            "Config": formatter.short(config_id, 20),
            "Comment": comment,
        },
    )


def _do_refresh(
    client: VPNClient, token: str, *, as_provider_for_user_id: int | None = None
) -> None:
    result = client.refresh_subscription(token, as_provider_for_user_id=as_provider_for_user_id)

    refreshed = result.refreshed or 0
    failed = result.failed or 0
    skipped = result.skipped or 0
    total = result.total or 0
    message = result.message
    errors = result.errors or []

    # 🔴 Полностью ничего не произошло
    if total == 0 and refreshed == 0 and failed == 0:
        console.print(
            Panel(
                f"[yellow]{message or 'Nothing to refresh'}[/yellow]",
                title="ⓘ No Action",
                border_style="yellow",
            )
        )
        return

    # 🟡 Только skipped (rate limit / cooldown)
    if refreshed == 0 and failed == 0 and skipped > 0:
        console.print(
            Panel(
                f"[yellow]Skipped {skipped} URL(s)[/yellow]\n\n{message or 'Cooldown active'}",
                title="⏳ Skipped",
                border_style="yellow",
            )
        )
        return

    # 🟢 Есть успешные обновления (даже если частично)
    if refreshed > 0:
        console.print(
            Panel(
                f"[green]✓ Refreshed:[/green] {refreshed}\n"
                f"[yellow]Skipped:[/yellow] {skipped}\n"
                f"[red]Failed:[/red] {failed}",
                title="✅ Refresh Complete",
                border_style="green" if failed == 0 else "yellow",
            )
        )
    else:
        # 🔴 Всё упало
        console.print(
            Panel(
                f"[red]Failed to refresh {failed} URL(s)[/red]",
                title="❌ Refresh Failed",
                border_style="red",
            )
        )

    # 🔴 Ошибки (если есть)
    if errors:
        console.print("\n[red]Errors:[/red]")
        for error in errors:
            console.print(f"  • {error}")


# ═══════════════════════════════════════════════════════════════════════════
# Regular Commands (Subscription Management)
# ═══════════════════════════════════════════════════════════════════════════


@app.command(name="list")
def sources_list(
    base_url: str | None = typer.Option(None, "--base-url", "-u", help="API base URL"),
    api_token: str | None = typer.Option(None, "--api-token", "-t", help="API token"),
) -> None:
    """List all subscriptions."""
    try:
        with ClientManager.get_client(base_url, api_token) as client:
            _do_list(client)

    except ValueError as e:
        formatter.show_missing_config(str(e))
        raise typer.Exit(1) from None
    except Exception as e:
        formatter.show_error(e)
        raise typer.Exit(1) from None


@app.command()
def create(
    name: str = typer.Argument(..., help="Subscription name"),
    description: str | None = typer.Option(None, "--description", "-d", help="Description"),
    sources: list[str] = typer.Option(
        [],
        "--source",
        "-s",
        help=(
            "Initial source: plain string, or JSON object for per-source "
            'options, e.g. \'{"data": "vless://...", "hidden": true, "depth": 0}\''
        ),
    ),
    base_url: str | None = typer.Option(None, "--base-url", "-u", help="API base URL"),
    api_token: str | None = typer.Option(None, "--api-token", "-t", help="API token"),
) -> None:
    """Create a new subscription."""
    try:
        with ClientManager.get_client(base_url, api_token) as client:
            _do_create(client, name, description, sources)

    except ValueError as e:
        formatter.show_missing_config(str(e))
        raise typer.Exit(1) from None
    except Exception as e:
        formatter.show_error(e)
        raise typer.Exit(1) from None


@app.command()
def get(
    token: str = typer.Argument(
        ..., help="Subscription token", shell_complete=complete_subscription_token
    ),
    base_url: str | None = typer.Option(None, "--base-url", "-u", help="API base URL"),
    api_token: str | None = typer.Option(None, "--api-token", "-t", help="API token"),
) -> None:
    """Get subscription details."""
    try:
        with ClientManager.get_client(base_url, api_token) as client:
            _do_get(client, token)

    except ValueError as e:
        formatter.show_missing_config(str(e))
        raise typer.Exit(1) from None
    except Exception as e:
        formatter.show_error(e)
        raise typer.Exit(1) from None


@app.command(name="add-sources")
def add_sources(
    token: str = typer.Argument(
        ..., help="Subscription token", shell_complete=complete_subscription_token
    ),
    sources: list[str] = typer.Option(
        ...,
        "--source",
        "-s",
        help=(
            "Source to add: plain string, or JSON object for per-source "
            'options, e.g. \'{"data": "vless://...", "hidden": true, "depth": 0}\''
        ),
    ),
    base_url: str | None = typer.Option(None, "--base-url", "-u", help="API base URL"),
    api_token: str | None = typer.Option(None, "--api-token", "-t", help="API token"),
) -> None:
    """Add sources to subscription."""
    try:
        with ClientManager.get_client(base_url, api_token) as client:
            _do_add_sources(client, token, sources)

    except ValueError as e:
        formatter.show_missing_config(str(e))
        raise typer.Exit(1) from None
    except Exception as e:
        formatter.show_error(e)
        raise typer.Exit(1) from None


@app.command(name="replace-sources")
def replace_sources(
    token: str = typer.Argument(
        ..., help="Subscription token", shell_complete=complete_subscription_token
    ),
    sources: list[str] = typer.Option(
        ...,
        "--source",
        "-s",
        help=(
            "Source to replace: plain string, or JSON object for per-source "
            'options, e.g. \'{"data": "vless://...", "hidden": true, "depth": 0}\''
        ),
    ),
    base_url: str | None = typer.Option(None, "--base-url", "-u", help="API base URL"),
    api_token: str | None = typer.Option(None, "--api-token", "-t", help="API token"),
) -> None:
    """Replace subscription's sources."""
    try:
        with ClientManager.get_client(base_url, api_token) as client:
            _do_replace_sources(client, token, sources)

    except ValueError as e:
        formatter.show_missing_config(str(e))
        raise typer.Exit(1) from None
    except Exception as e:
        formatter.show_error(e)
        raise typer.Exit(1) from None


@app.command(name="remove-sources")
def remove_sources(
    token: str = typer.Argument(
        ..., help="Subscription token", shell_complete=complete_subscription_token
    ),
    sources: list[str] = typer.Option(..., "--source", "-s", help="Sources to remove"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
    base_url: str | None = typer.Option(None, "--base-url", "-u", help="API base URL"),
    api_token: str | None = typer.Option(None, "--api-token", "-t", help="API token"),
) -> None:
    """Remove sources from subscription."""
    try:
        with ClientManager.get_client(base_url, api_token) as client:
            _do_remove_sources(client, token, sources, force)

    except ValueError as e:
        formatter.show_missing_config(str(e))
        raise typer.Exit(1) from None
    except Exception as e:
        formatter.show_error(e)
        raise typer.Exit(1) from None


@app.command()
def delete(
    token: str = typer.Argument(
        ..., help="Subscription token", shell_complete=complete_subscription_token
    ),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
    base_url: str | None = typer.Option(None, "--base-url", "-u", help="API base URL"),
    api_token: str | None = typer.Option(None, "--api-token", "-t", help="API token"),
) -> None:
    """Delete subscription."""
    try:
        with ClientManager.get_client(base_url, api_token) as client:
            _do_delete(client, token, force)

    except ValueError as e:
        formatter.show_missing_config(str(e))
        raise typer.Exit(1) from None
    except Exception as e:
        formatter.show_error(e)
        raise typer.Exit(1) from None


@app.command()
def update(
    token: str = typer.Argument(
        ..., help="Subscription token", shell_complete=complete_subscription_token
    ),
    name: str | None = typer.Option(None, "--name", "-n", help="New subscription name"),
    description: str | None = typer.Option(None, "--description", "-d", help="New description"),
    base_url: str | None = typer.Option(None, "--base-url", "-u", help="API base URL"),
    api_token: str | None = typer.Option(None, "--api-token", "-t", help="API token"),
) -> None:
    """Update subscription's name and/or description."""
    try:
        with ClientManager.get_client(base_url, api_token) as client:
            _do_update(client, token, name, description)

    except ValueError as e:
        formatter.show_missing_config(str(e))
        raise typer.Exit(1) from None
    except Exception as e:
        formatter.show_error(e)
        raise typer.Exit(1) from None


@app.command(name="update-config")
def update_config(
    token: str = typer.Argument(
        ..., help="Subscription token", shell_complete=complete_subscription_token
    ),
    config_id: str = typer.Option(
        ..., "--config-id", "-i", help="Config ID", shell_complete=complete_config_hash
    ),
    comment: str | None = typer.Option(None, "--comment", "-c", help="New config comment"),
    hidden: bool | None = typer.Option(
        None,
        "--hidden/--visible",
        help="Hide or unhide this source's configs from end users",
    ),
    max_depth: int | None = typer.Option(
        None,
        "--max-depth",
        min=0,
        max=3,
        help="Max nesting depth for this source (0-3)",
    ),
    base_url: str | None = typer.Option(None, "--base-url", "-u", help="API base URL"),
    api_token: str | None = typer.Option(None, "--api-token", "-t", help="API token"),
) -> None:
    """
    Update a config's settings within a subscription.

    Replaces the deprecated 'update-comment' command: supports the same
    comment update, plus --hidden/--visible and --max-depth. Only the
    fields you pass are changed; everything else is left as-is.
    """
    try:
        with ClientManager.get_client(base_url, api_token) as client:
            _do_update_config(client, token, config_id, comment, hidden, max_depth)

    except ValueError as e:
        formatter.show_missing_config(str(e))
        raise typer.Exit(1) from None
    except Exception as e:
        formatter.show_error(e)
        raise typer.Exit(1) from None


@app.command(
    name="update-comment",
    hidden=True,
    help="[Deprecated: use 'update-config' instead] Update comment for a config inside subscription.",
)
def update_comment(
    token: str = typer.Argument(
        ..., help="Subscription token", shell_complete=complete_subscription_token
    ),
    config_id: str = typer.Option(
        ..., "--config-id", "-i", help="Config ID", shell_complete=complete_config_hash
    ),
    comment: str = typer.Option(..., "--comment", "-c", help="New config comment"),
    base_url: str | None = typer.Option(None, "--base-url", "-u", help="API base URL"),
    api_token: str | None = typer.Option(None, "--api-token", "-t", help="API token"),
) -> None:
    """
    [Deprecated] Update comment for a config inside subscription.

    This command still works and is fully supported, but will not
    receive further updates and may be removed in a future major
    version. Use 'update-config' instead, which supports the same
    comment update plus --hidden/--visible and --max-depth.
    """
    try:
        with ClientManager.get_client(base_url, api_token) as client:
            _do_update_comment(client, token, config_id, comment)

    except ValueError as e:
        formatter.show_missing_config(str(e))
        raise typer.Exit(1) from None
    except Exception as e:
        formatter.show_error(e)
        raise typer.Exit(1) from None


@app.command()
def refresh(
    token: str = typer.Argument(
        ..., help="Subscription token", shell_complete=complete_subscription_token
    ),
    base_url: str | None = typer.Option(None, "--base-url", "-u", help="API base URL"),
    api_token: str | None = typer.Option(None, "--api-token", "-t", help="API token"),
) -> None:
    """Refresh external URL sources."""
    try:
        with ClientManager.get_client(base_url, api_token) as client:
            _do_refresh(client, token)

    except ValueError as e:
        formatter.show_missing_config(str(e))
        raise typer.Exit(1) from None
    except Exception as e:
        formatter.show_error(e)
        raise typer.Exit(1) from None


# ═══════════════════════════════════════════════════════════════════════════
# Account & Public Access
# ═══════════════════════════════════════════════════════════════════════════


@app.command()
def me(
    base_url: str | None = typer.Option(None, "--base-url", "-u", help="API base URL"),
    api_token: str | None = typer.Option(None, "--api-token", "-t", help="API token"),
) -> None:
    """Show information about the currently authenticated user."""
    try:
        with ClientManager.get_client(base_url, api_token) as client:
            result = client.get_me()
            formatter.show_me(result)

    except ValueError as e:
        formatter.show_missing_config(str(e))
        raise typer.Exit(1) from None
    except Exception as e:
        formatter.show_error(e)
        raise typer.Exit(1) from None


@app.command()
def public(
    token: str = typer.Argument(
        ..., help="Subscription token", shell_complete=complete_subscription_token
    ),
    decode: bool = typer.Option(
        False, "--decode", "-d", help="Decode and print the configs instead of base64"
    ),
    base_url: str | None = typer.Option(None, "--base-url", "-u", help="API base URL"),
    api_token: str | None = typer.Option(
        None,
        "--api-token",
        "-t",
        help="API token (the public-configs endpoint itself doesn't require one to belong "
        "to this subscription, but the client still needs a valid token to authenticate)",
    ),
) -> None:
    """Fetch a subscription's public configs."""
    try:
        with ClientManager.get_client(base_url, api_token) as client:
            result = client.get_public_subscription(token)
            formatter.show_public_subscription(result, decode=decode)

    except ValueError as e:
        formatter.show_missing_config(str(e))
        raise typer.Exit(1) from None
    except Exception as e:
        formatter.show_error(e)
        raise typer.Exit(1) from None


# ═══════════════════════════════════════════════════════════════════════════
# Provider Connections (self-service side)
# ═══════════════════════════════════════════════════════════════════════════
#
# These operate on the *current* authenticated user's own connections to
# providers -- the mirror image of `provider {user_id} connection-*`
# below, which operates from a provider's point of view about one of
# their users. Nothing here talks HTTP directly; every command calls the
# matching method on `v2hub.client.VPNClient`.

connection_app = typer.Typer(
    name="connection",
    help="Manage the current user's connections to providers.",
)
app.add_typer(connection_app, name="connection")


@connection_app.command(name="list")
def connection_list(
    base_url: str | None = typer.Option(None, "--base-url", "-u", help="API base URL"),
    api_token: str | None = typer.Option(None, "--api-token", "-t", help="API token"),
) -> None:
    """List the current user's provider connections (pending and approved)."""
    try:
        with ClientManager.get_client(base_url, api_token) as client:
            result = client.list_connections()
            formatter.show_connections_table(result.connections)

    except ValueError as e:
        formatter.show_missing_config(str(e))
        raise typer.Exit(1) from None
    except Exception as e:
        formatter.show_error(e)
        raise typer.Exit(1) from None


@connection_app.command(name="get")
def connection_get(
    provider_name: str = typer.Argument(..., help="Public provider name"),
    base_url: str | None = typer.Option(None, "--base-url", "-u", help="API base URL"),
    api_token: str | None = typer.Option(None, "--api-token", "-t", help="API token"),
) -> None:
    """Get the current user's connection status for a provider."""
    try:
        with ClientManager.get_client(base_url, api_token) as client:
            result = client.get_connection(provider_name)
            formatter.show_connection(result)

    except ValueError as e:
        formatter.show_missing_config(str(e))
        raise typer.Exit(1) from None
    except Exception as e:
        formatter.show_error(e)
        raise typer.Exit(1) from None


@connection_app.command(name="approve")
def connection_approve(
    provider_name: str = typer.Argument(..., help="Public provider name"),
    base_url: str | None = typer.Option(None, "--base-url", "-u", help="API base URL"),
    api_token: str | None = typer.Option(None, "--api-token", "-t", help="API token"),
) -> None:
    """Approve a pending provider connection request."""
    try:
        with ClientManager.get_client(base_url, api_token) as client:
            result = client.approve_connection(provider_name)
            formatter.show_connection(result, title="✅ Connection Approved")

    except ValueError as e:
        formatter.show_missing_config(str(e))
        raise typer.Exit(1) from None
    except Exception as e:
        formatter.show_error(e)
        raise typer.Exit(1) from None


@connection_app.command(name="reject")
def connection_reject(
    provider_name: str = typer.Argument(..., help="Public provider name"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
    base_url: str | None = typer.Option(None, "--base-url", "-u", help="API base URL"),
    api_token: str | None = typer.Option(None, "--api-token", "-t", help="API token"),
) -> None:
    """Reject a pending provider connection request."""
    try:
        if not force:
            confirm = typer.confirm(f"Reject pending connection to provider '{provider_name}'?")
            if not confirm:
                console.print("[yellow]Cancelled[/yellow]")
                return

        with ClientManager.get_client(base_url, api_token) as client:
            result = client.reject_connection(provider_name)
            formatter.show_connection(result, title="🚫 Connection Rejected")

    except ValueError as e:
        formatter.show_missing_config(str(e))
        raise typer.Exit(1) from None
    except Exception as e:
        formatter.show_error(e)
        raise typer.Exit(1) from None


@connection_app.command(name="revoke")
def connection_revoke(
    provider_name: str = typer.Argument(..., help="Public provider name"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
    base_url: str | None = typer.Option(None, "--base-url", "-u", help="API base URL"),
    api_token: str | None = typer.Option(None, "--api-token", "-t", help="API token"),
) -> None:
    """Revoke the current user's authorization for a provider.

    Existing subscriptions from that provider remain available; the
    authorization record is preserved as REVOKED rather than deleted.
    """
    try:
        if not force:
            confirm = typer.confirm(f"Revoke connection to provider '{provider_name}'?")
            if not confirm:
                console.print("[yellow]Cancelled[/yellow]")
                return

        with ClientManager.get_client(base_url, api_token) as client:
            client.revoke_connection(provider_name)
            formatter.show_success(
                f"Revoked connection to provider [cyan]{provider_name}[/cyan]",
                title="🚫 Connection Revoked",
            )

    except ValueError as e:
        formatter.show_missing_config(str(e))
        raise typer.Exit(1) from None
    except Exception as e:
        formatter.show_error(e)
        raise typer.Exit(1) from None


# ═══════════════════════════════════════════════════════════════════════════
# Provider Commands
# ═══════════════════════════════════════════════════════════════════════════
#
# `v2hub provider {user_id} COMMAND` -- every subscription command above is
# available here too, targeting a specific end-user on behalf of a
# provider. `user_id` is captured once by the group callback (so it's
# typed `v2hub provider 123 list`, matching the requested syntax) and
# reused by every subcommand below via `ctx.obj["user_id"]`.
#
# No HTTP or auth logic lives here: `ClientManager.get_client()` returns
# the exact same `VPNClient` used for self-service, and `user_id` is
# forwarded as `as_provider_for_user_id` into the shared `_do_*` helpers
# above -- which is what actually makes `v2hub.client.VPNClient` route the
# request to `/providers/{user_id}/subs/...` and apply provider
# authorization. The provider token is whatever `--api-token` /
# `V2HUB_API_TOKEN` resolves to; nothing here treats it differently from
# a regular user token -- that distinction is entirely v2hub's/the
# server's responsibility, not the CLI's.

provider_app = typer.Typer(
    name="provider",
    help="Manage subscriptions and connections on behalf of a specific end-user.",
)
app.add_typer(provider_app, name="provider")


@provider_app.callback()
def provider_context(
    ctx: typer.Context,
    user_id: int = typer.Argument(..., help="Target end-user's numeric ID"),
) -> None:
    """Operate on behalf of the given end-user (provider mode)."""
    ctx.obj = {"user_id": user_id}


def _provider_user_id(ctx: typer.Context) -> int:
    obj = ctx.obj
    if not isinstance(obj, dict) or "user_id" not in obj:  # pragma: no cover - defensive
        raise typer.BadParameter("provider user_id is required")
    return int(obj["user_id"])


# ─────────────────────── Connection lifecycle ───────────────────────


@provider_app.command(name="connection-get")
def provider_connection_get(
    ctx: typer.Context,
    base_url: str | None = typer.Option(None, "--base-url", "-u", help="API base URL"),
    api_token: str | None = typer.Option(None, "--api-token", "-t", help="Provider API token"),
) -> None:
    """Get the current authorization status between this provider and the user."""
    user_id = _provider_user_id(ctx)
    try:
        with ClientManager.get_client(base_url, api_token) as client:
            conn = client.get_provider_connection(user_id)
            formatter.show_provider_connection(conn)

    except ValueError as e:
        formatter.show_missing_config(str(e))
        raise typer.Exit(1) from None
    except Exception as e:
        formatter.show_error(e)
        raise typer.Exit(1) from None


@provider_app.command(name="connection-create")
def provider_connection_create(
    ctx: typer.Context,
    base_url: str | None = typer.Option(None, "--base-url", "-u", help="API base URL"),
    api_token: str | None = typer.Option(None, "--api-token", "-t", help="Provider API token"),
) -> None:
    """Create (or re-request/activate) a connection to the user."""
    user_id = _provider_user_id(ctx)
    try:
        with ClientManager.get_client(base_url, api_token) as client:
            conn = client.create_provider_connection(user_id)
            formatter.show_provider_connection(conn, title="🔗 Connection Created")

    except ValueError as e:
        formatter.show_missing_config(str(e))
        raise typer.Exit(1) from None
    except Exception as e:
        formatter.show_error(e)
        raise typer.Exit(1) from None


@provider_app.command(name="connection-revoke")
def provider_connection_revoke(
    ctx: typer.Context,
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
    base_url: str | None = typer.Option(None, "--base-url", "-u", help="API base URL"),
    api_token: str | None = typer.Option(None, "--api-token", "-t", help="Provider API token"),
) -> None:
    """Revoke this provider's authorization for the user (connection record is kept)."""
    user_id = _provider_user_id(ctx)
    try:
        if not force:
            confirm = typer.confirm(f"Revoke connection to user {user_id}?")
            if not confirm:
                console.print("[yellow]Cancelled[/yellow]")
                return

        with ClientManager.get_client(base_url, api_token) as client:
            conn = client.revoke_provider_connection(user_id)
            formatter.show_provider_connection(conn, title="🚫 Connection Revoked")

    except ValueError as e:
        formatter.show_missing_config(str(e))
        raise typer.Exit(1) from None
    except Exception as e:
        formatter.show_error(e)
        raise typer.Exit(1) from None


@provider_app.command(name="connection-delete")
def provider_connection_delete(
    ctx: typer.Context,
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
    base_url: str | None = typer.Option(None, "--base-url", "-u", help="API base URL"),
    api_token: str | None = typer.Option(None, "--api-token", "-t", help="Provider API token"),
) -> None:
    """Permanently delete the connection record to the user."""
    user_id = _provider_user_id(ctx)
    try:
        if not force:
            confirm = typer.confirm(f"Permanently delete connection to user {user_id}?")
            if not confirm:
                console.print("[yellow]Cancelled[/yellow]")
                return

        with ClientManager.get_client(base_url, api_token) as client:
            result = client.delete_provider_connection(user_id)
            formatter.show_success(result.detail, title="🗑️ Connection Deleted")

    except ValueError as e:
        formatter.show_missing_config(str(e))
        raise typer.Exit(1) from None
    except Exception as e:
        formatter.show_error(e)
        raise typer.Exit(1) from None


# ─────────────────────── Subscription commands (provider context) ───────────────────────


@provider_app.command(name="list")
def provider_list(
    ctx: typer.Context,
    base_url: str | None = typer.Option(None, "--base-url", "-u", help="API base URL"),
    api_token: str | None = typer.Option(None, "--api-token", "-t", help="Provider API token"),
) -> None:
    """List the user's subscriptions."""
    user_id = _provider_user_id(ctx)
    try:
        with ClientManager.get_client(base_url, api_token) as client:
            _do_list(client, as_provider_for_user_id=user_id)

    except ValueError as e:
        formatter.show_missing_config(str(e))
        raise typer.Exit(1) from None
    except Exception as e:
        formatter.show_error(e)
        raise typer.Exit(1) from None


@provider_app.command(name="create")
def provider_create(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Subscription name"),
    description: str | None = typer.Option(None, "--description", "-d", help="Description"),
    sources: list[str] = typer.Option(
        [],
        "--source",
        "-s",
        help=(
            "Initial source: plain string, or JSON object for per-source "
            'options, e.g. \'{"data": "vless://...", "hidden": true, "depth": 0}\''
        ),
    ),
    base_url: str | None = typer.Option(None, "--base-url", "-u", help="API base URL"),
    api_token: str | None = typer.Option(None, "--api-token", "-t", help="Provider API token"),
) -> None:
    """Create a new subscription for the user."""
    user_id = _provider_user_id(ctx)
    try:
        with ClientManager.get_client(base_url, api_token) as client:
            _do_create(client, name, description, sources, as_provider_for_user_id=user_id)

    except ValueError as e:
        formatter.show_missing_config(str(e))
        raise typer.Exit(1) from None
    except Exception as e:
        formatter.show_error(e)
        raise typer.Exit(1) from None


@provider_app.command(name="get")
def provider_get(
    ctx: typer.Context,
    token: str = typer.Argument(
        ..., help="Subscription token", shell_complete=complete_provider_subscription_token
    ),
    base_url: str | None = typer.Option(None, "--base-url", "-u", help="API base URL"),
    api_token: str | None = typer.Option(None, "--api-token", "-t", help="Provider API token"),
) -> None:
    """Get subscription details for the user."""
    user_id = _provider_user_id(ctx)
    try:
        with ClientManager.get_client(base_url, api_token) as client:
            _do_get(client, token, as_provider_for_user_id=user_id)

    except ValueError as e:
        formatter.show_missing_config(str(e))
        raise typer.Exit(1) from None
    except Exception as e:
        formatter.show_error(e)
        raise typer.Exit(1) from None


@provider_app.command(name="add-sources")
def provider_add_sources(
    ctx: typer.Context,
    token: str = typer.Argument(
        ..., help="Subscription token", shell_complete=complete_provider_subscription_token
    ),
    sources: list[str] = typer.Option(
        ...,
        "--source",
        "-s",
        help=(
            "Source to add: plain string, or JSON object for per-source "
            'options, e.g. \'{"data": "vless://...", "hidden": true, "depth": 0}\''
        ),
    ),
    base_url: str | None = typer.Option(None, "--base-url", "-u", help="API base URL"),
    api_token: str | None = typer.Option(None, "--api-token", "-t", help="Provider API token"),
) -> None:
    """Add sources to the user's subscription."""
    user_id = _provider_user_id(ctx)
    try:
        with ClientManager.get_client(base_url, api_token) as client:
            _do_add_sources(client, token, sources, as_provider_for_user_id=user_id)

    except ValueError as e:
        formatter.show_missing_config(str(e))
        raise typer.Exit(1) from None
    except Exception as e:
        formatter.show_error(e)
        raise typer.Exit(1) from None


@provider_app.command(name="replace-sources")
def provider_replace_sources(
    ctx: typer.Context,
    token: str = typer.Argument(
        ..., help="Subscription token", shell_complete=complete_provider_subscription_token
    ),
    sources: list[str] = typer.Option(
        ...,
        "--source",
        "-s",
        help=(
            "Source to replace: plain string, or JSON object for per-source "
            'options, e.g. \'{"data": "vless://...", "hidden": true, "depth": 0}\''
        ),
    ),
    base_url: str | None = typer.Option(None, "--base-url", "-u", help="API base URL"),
    api_token: str | None = typer.Option(None, "--api-token", "-t", help="Provider API token"),
) -> None:
    """Replace the user's subscription sources."""
    user_id = _provider_user_id(ctx)
    try:
        with ClientManager.get_client(base_url, api_token) as client:
            _do_replace_sources(client, token, sources, as_provider_for_user_id=user_id)

    except ValueError as e:
        formatter.show_missing_config(str(e))
        raise typer.Exit(1) from None
    except Exception as e:
        formatter.show_error(e)
        raise typer.Exit(1) from None


@provider_app.command(name="remove-sources")
def provider_remove_sources(
    ctx: typer.Context,
    token: str = typer.Argument(
        ..., help="Subscription token", shell_complete=complete_provider_subscription_token
    ),
    sources: list[str] = typer.Option(..., "--source", "-s", help="Sources to remove"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
    base_url: str | None = typer.Option(None, "--base-url", "-u", help="API base URL"),
    api_token: str | None = typer.Option(None, "--api-token", "-t", help="Provider API token"),
) -> None:
    """Remove sources from the user's subscription."""
    user_id = _provider_user_id(ctx)
    try:
        with ClientManager.get_client(base_url, api_token) as client:
            _do_remove_sources(client, token, sources, force, as_provider_for_user_id=user_id)

    except ValueError as e:
        formatter.show_missing_config(str(e))
        raise typer.Exit(1) from None
    except Exception as e:
        formatter.show_error(e)
        raise typer.Exit(1) from None


@provider_app.command(name="delete")
def provider_delete(
    ctx: typer.Context,
    token: str = typer.Argument(
        ..., help="Subscription token", shell_complete=complete_provider_subscription_token
    ),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
    base_url: str | None = typer.Option(None, "--base-url", "-u", help="API base URL"),
    api_token: str | None = typer.Option(None, "--api-token", "-t", help="Provider API token"),
) -> None:
    """Delete the user's subscription."""
    user_id = _provider_user_id(ctx)
    try:
        with ClientManager.get_client(base_url, api_token) as client:
            _do_delete(client, token, force, as_provider_for_user_id=user_id)

    except ValueError as e:
        formatter.show_missing_config(str(e))
        raise typer.Exit(1) from None
    except Exception as e:
        formatter.show_error(e)
        raise typer.Exit(1) from None


@provider_app.command(name="update")
def provider_update(
    ctx: typer.Context,
    token: str = typer.Argument(
        ..., help="Subscription token", shell_complete=complete_provider_subscription_token
    ),
    name: str | None = typer.Option(None, "--name", "-n", help="New subscription name"),
    description: str | None = typer.Option(None, "--description", "-d", help="New description"),
    base_url: str | None = typer.Option(None, "--base-url", "-u", help="API base URL"),
    api_token: str | None = typer.Option(None, "--api-token", "-t", help="Provider API token"),
) -> None:
    """Update the user's subscription name and/or description."""
    user_id = _provider_user_id(ctx)
    try:
        with ClientManager.get_client(base_url, api_token) as client:
            _do_update(client, token, name, description, as_provider_for_user_id=user_id)

    except ValueError as e:
        formatter.show_missing_config(str(e))
        raise typer.Exit(1) from None
    except Exception as e:
        formatter.show_error(e)
        raise typer.Exit(1) from None


@provider_app.command(name="update-config")
def provider_update_config(
    ctx: typer.Context,
    token: str = typer.Argument(
        ..., help="Subscription token", shell_complete=complete_provider_subscription_token
    ),
    config_id: str = typer.Option(
        ..., "--config-id", "-i", help="Config ID", shell_complete=complete_config_hash
    ),
    comment: str | None = typer.Option(None, "--comment", "-c", help="New config comment"),
    hidden: bool | None = typer.Option(
        None,
        "--hidden/--visible",
        help="Hide or unhide this source's configs from end users",
    ),
    max_depth: int | None = typer.Option(
        None,
        "--max-depth",
        min=0,
        max=3,
        help="Max nesting depth for this source (0-3)",
    ),
    base_url: str | None = typer.Option(None, "--base-url", "-u", help="API base URL"),
    api_token: str | None = typer.Option(None, "--api-token", "-t", help="Provider API token"),
) -> None:
    """Update a config's settings within the user's subscription."""
    user_id = _provider_user_id(ctx)
    try:
        with ClientManager.get_client(base_url, api_token) as client:
            _do_update_config(
                client,
                token,
                config_id,
                comment,
                hidden,
                max_depth,
                as_provider_for_user_id=user_id,
            )

    except ValueError as e:
        formatter.show_missing_config(str(e))
        raise typer.Exit(1) from None
    except Exception as e:
        formatter.show_error(e)
        raise typer.Exit(1) from None


@provider_app.command(name="refresh")
def provider_refresh(
    ctx: typer.Context,
    token: str = typer.Argument(
        ..., help="Subscription token", shell_complete=complete_provider_subscription_token
    ),
    base_url: str | None = typer.Option(None, "--base-url", "-u", help="API base URL"),
    api_token: str | None = typer.Option(None, "--api-token", "-t", help="Provider API token"),
) -> None:
    """Refresh external URL sources on the user's subscription."""
    user_id = _provider_user_id(ctx)
    try:
        with ClientManager.get_client(base_url, api_token) as client:
            _do_refresh(client, token, as_provider_for_user_id=user_id)

    except ValueError as e:
        formatter.show_missing_config(str(e))
        raise typer.Exit(1) from None
    except Exception as e:
        formatter.show_error(e)
        raise typer.Exit(1) from None


# ═══════════════════════════════════════════════════════════════════════════
# Main Entry Point
# ═══════════════════════════════════════════════════════════════════════════


def main() -> None:
    """Main CLI entry point."""
    from v2hub_cli.cli_autocomplete_setup import maybe_install_completion

    maybe_install_completion()
    app()


if __name__ == "__main__":
    main()
