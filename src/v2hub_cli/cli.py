"""
Unified CLI for VPN Subscription API.

Beautiful command-line interface with both regular and admin functionality.
"""

from __future__ import annotations

import json
from importlib.metadata import PackageNotFoundError, version
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel

from v2hub.models.requests import SourceCreate
from v2hub_cli import __version__ as cli_version
from v2hub_cli.cli_formatter import OutputFormatter
from v2hub_cli.cli_manager import ClientManager

app = typer.Typer(
    name="v2hub",
    help="VPN Subscription API Client CLI",
    add_completion=False,
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
            subs = client.list_subscriptions()

            if not subs:
                console.print("[yellow]No subscriptions found[/yellow]")
                return

            table = formatter.create_subscription_table(subs)
            console.print(table)

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
            sub = client.create_subscription(name, description, _build_sources(sources))

            formatter.show_success(
                f"Created subscription: [cyan]{sub.name}[/cyan]",
                details={
                    "Token": f"[green]{sub.token}[/green]",
                    "Sources": f"[yellow]{sub.sources_count}[/yellow]",
                },
            )

    except ValueError as e:
        formatter.show_missing_config(str(e))
        raise typer.Exit(1) from None
    except Exception as e:
        formatter.show_error(e)
        raise typer.Exit(1) from None


@app.command()
def get(
    token: str = typer.Argument(..., help="Subscription token"),
    base_url: str | None = typer.Option(None, "--base-url", "-u", help="API base URL"),
    api_token: str | None = typer.Option(None, "--api-token", "-t", help="API token"),
) -> None:
    """Get subscription details."""
    try:
        with ClientManager.get_client(base_url, api_token) as client:
            sub = client.get_subscription(token)
            formatter.show_subscription_detail(sub)

    except ValueError as e:
        formatter.show_missing_config(str(e))
        raise typer.Exit(1) from None
    except Exception as e:
        formatter.show_error(e)
        raise typer.Exit(1) from None


@app.command(name="add-sources")
def add_sources(
    token: str = typer.Argument(..., help="Subscription token"),
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
            sub = client.add_sources(token, _build_sources(sources))

            formatter.show_success(
                f"Added [bold]{len(sources)}[/bold] source(s)",
                title="✅ Sources Updated",
                details={
                    "Total configs": f"[yellow]{sub.sources_count}[/yellow]",
                },
            )

    except ValueError as e:
        formatter.show_missing_config(str(e))
        raise typer.Exit(1) from None
    except Exception as e:
        formatter.show_error(e)
        raise typer.Exit(1) from None


@app.command(name="replace-sources")
def replace_sources(
    token: str = typer.Argument(..., help="Subscription token"),
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
            sub = client.replace_sources(token, _build_sources(sources))

            formatter.show_success(
                "Sources replaced",
                title="✅ Sources Replaced",
                details={
                    "Total configs": f"[yellow]{sub.sources_count}[/yellow]",
                },
            )

    except ValueError as e:
        formatter.show_missing_config(str(e))
        raise typer.Exit(1) from None
    except Exception as e:
        formatter.show_error(e)
        raise typer.Exit(1) from None


@app.command(name="remove-sources")
def remove_sources(
    token: str = typer.Argument(..., help="Subscription token"),
    sources: list[str] = typer.Option(..., "--source", "-s", help="Sources to remove"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
    base_url: str | None = typer.Option(None, "--base-url", "-u", help="API base URL"),
    api_token: str | None = typer.Option(None, "--api-token", "-t", help="API token"),
) -> None:
    """Remove sources from subscription."""
    try:
        # Confirmation
        if not force:
            source_list = ", ".join(sources)
            confirm = typer.confirm(
                f"Remove sources [blue]{source_list}[/blue] from subscription [cyan]{token}[/cyan]?"
            )
            if not confirm:
                console.print("[yellow]Cancelled[/yellow]")
                return

        with ClientManager.get_client(base_url, api_token) as client:
            sub = client.remove_sources(token, sources)

            formatter.show_success(
                f"Removed [bold]{len(sources)}[/bold] source(s)",
                title="✅ Sources Updated",
                details={
                    "Total configs": f"[yellow]{sub.sources_count}[/yellow]",
                },
            )

    except ValueError as e:
        formatter.show_missing_config(str(e))
        raise typer.Exit(1) from None
    except Exception as e:
        formatter.show_error(e)
        raise typer.Exit(1) from None


@app.command()
def delete(
    token: str = typer.Argument(..., help="Subscription token"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
    base_url: str | None = typer.Option(None, "--base-url", "-u", help="API base URL"),
    api_token: str | None = typer.Option(None, "--api-token", "-t", help="API token"),
) -> None:
    """Delete subscription."""
    try:
        if not force:
            confirm = typer.confirm(f"Delete subscription {token}?")
            if not confirm:
                console.print("[yellow]Cancelled[/yellow]")
                return

        with ClientManager.get_client(base_url, api_token) as client:
            client.delete_subscription(token)

            formatter.show_success(f"Deleted subscription: [cyan]{token}[/cyan]")

    except ValueError as e:
        formatter.show_missing_config(str(e))
        raise typer.Exit(1) from None
    except Exception as e:
        formatter.show_error(e)
        raise typer.Exit(1) from None


@app.command()
def update(
    token: str = typer.Argument(..., help="Subscription token"),
    name: str | None = typer.Option(None, "--name", "-n", help="New subscription name"),
    description: str | None = typer.Option(None, "--description", "-d", help="New description"),
    base_url: str | None = typer.Option(None, "--base-url", "-u", help="API base URL"),
    api_token: str | None = typer.Option(None, "--api-token", "-t", help="API token"),
) -> None:
    """Update subscription's name and/or description."""
    try:
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

        with ClientManager.get_client(base_url, api_token) as client:
            client.update_subscription(token, name, description)

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

    except ValueError as e:
        formatter.show_missing_config(str(e))
        raise typer.Exit(1) from None
    except Exception as e:
        formatter.show_error(e)
        raise typer.Exit(1) from None


@app.command(name="update-config")
def update_config(
    token: str = typer.Argument(..., help="Subscription token"),
    config_id: str = typer.Option(..., "--config-id", "-i", help="Config ID"),
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

    try:
        with ClientManager.get_client(base_url, api_token) as client:
            client.update_source(
                token,
                config_id,
                comment=comment,
                is_hidden=hidden,
                max_depth=max_depth,
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
    token: str = typer.Argument(..., help="Subscription token"),
    config_id: str = typer.Option(..., "--config-id", "-i", help="Config ID"),
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
    console.print(
        "[yellow]⚠ 'update-comment' is deprecated and will not receive "
        "further updates. Use 'update-config' instead.[/yellow]"
    )
    try:
        with ClientManager.get_client(base_url, api_token) as client:
            client.update_comment(token, config_id, comment)

            formatter.show_success(
                "Comment updated successfully",
                title="Updated",
                details={
                    "Config": formatter.short(config_id, 20),
                    "Comment": comment,
                },
            )

    except ValueError as e:
        formatter.show_missing_config(str(e))
        raise typer.Exit(1) from None
    except Exception as e:
        formatter.show_error(e)
        raise typer.Exit(1) from None


@app.command()
def refresh(
    token: str = typer.Argument(..., help="Subscription token"),
    base_url: str | None = typer.Option(None, "--base-url", "-u", help="API base URL"),
    api_token: str | None = typer.Option(None, "--api-token", "-t", help="API token"),
) -> None:
    """Refresh external URL sources."""
    try:
        with ClientManager.get_client(base_url, api_token) as client:
            result = client.refresh_subscription(token)

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
                        f"[yellow]Skipped {skipped} URL(s)[/yellow]\n\n"
                        f"{message or 'Cooldown active'}",
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
    app()


if __name__ == "__main__":
    main()
