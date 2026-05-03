"""
Unified CLI for VPN Subscription API.

Beautiful command-line interface with both regular and admin functionality.
"""
from __future__ import annotations
from typing import List

import typer
from rich.console import Console
from rich.panel import Panel

from v2hub import __version__
from v2hub_cli.cli_formatter import OutputFormatter
from v2hub_cli.cli_manager import ClientManager

app = typer.Typer(
    name="v2hub",
    help="VPN Subscription API Client CLI",
    add_completion=False,
)

console = Console()
formatter = OutputFormatter(console)


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
# Version Command
# ═══════════════════════════════════════════════════════════════════════════


@app.command()
def version() -> None:
    """Show version information."""
    formatter.show_version(__version__)


# ═══════════════════════════════════════════════════════════════════════════
# Regular Commands (Subscription Management)
# ═══════════════════════════════════════════════════════════════════════════


@app.command()
def list(
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
        raise typer.Exit(1)
    except Exception as e:
        formatter.show_error(e)
        raise typer.Exit(1)


@app.command()
def create(
    name: str = typer.Argument(..., help="Subscription name"),
    description: str | None = typer.Option(None, "--description", "-d", help="Description"),
    sources: List[str] = typer.Option([], "--source", "-s", help="Initial sources"),
    base_url: str | None = typer.Option(None, "--base-url", "-u", help="API base URL"),
    api_token: str | None = typer.Option(None, "--api-token", "-t", help="API token"),
) -> None:
    """Create a new subscription."""
    try:
        with ClientManager.get_client(base_url, api_token) as client:
            sub = client.create_subscription(name, description, sources)

            formatter.show_success(
                f"Created subscription: [cyan]{sub.name}[/cyan]",
                details={
                    "Token": f"[green]{sub.token}[/green]",
                    "Sources": f"[yellow]{sub.sources_count}[/yellow]",
                },
            )

    except ValueError as e:
        formatter.show_missing_config(str(e))
        raise typer.Exit(1)
    except Exception as e:
        formatter.show_error(e)
        raise typer.Exit(1)


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
        raise typer.Exit(1)
    except Exception as e:
        formatter.show_error(e)
        raise typer.Exit(1)


@app.command()
def add_sources(
    token: str = typer.Argument(..., help="Subscription token"),
    sources: List[str] = typer.Option(..., "--source", "-s", help="Sources to add"),
    base_url: str | None = typer.Option(None, "--base-url", "-u", help="API base URL"),
    api_token: str | None = typer.Option(None, "--api-token", "-t", help="API token"),
) -> None:
    """Add sources to subscription."""
    try:
        with ClientManager.get_client(base_url, api_token) as client:
            sub = client.add_sources(token, sources)

            formatter.show_success(
                f"Added [bold]{len(sources)}[/bold] source(s)",
                title="✅ Sources Updated",
                details={
                    "Total configs": f"[yellow]{sub.sources_count}[/yellow]",
                },
            )

    except ValueError as e:
        formatter.show_missing_config(str(e))
        raise typer.Exit(1)
    except Exception as e:
        formatter.show_error(e)
        raise typer.Exit(1)


@app.command()
def remove_sources(
    token: str = typer.Argument(..., help="Subscription token"),
    sources: List[str] = typer.Option(..., "--source", "-s", help="Sources to remove"),
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
        raise typer.Exit(1)
    except Exception as e:
        formatter.show_error(e)
        raise typer.Exit(1)


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

            formatter.show_success(
                f"Deleted subscription: [cyan]{token}[/cyan]"
            )

    except ValueError as e:
        formatter.show_missing_config(str(e))
        raise typer.Exit(1)
    except Exception as e:
        formatter.show_error(e)
        raise typer.Exit(1)


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
        raise typer.Exit(1)
    except Exception as e:
        formatter.show_error(e)
        raise typer.Exit(1)


@app.command()
def update_comment(
    token: str = typer.Argument(..., help="Subscription token"),
    config_id: str = typer.Option(..., "--config-id", "-i", help="Config ID"),
    comment: str = typer.Option(..., "--comment", "-c", help="New config comment"),
    base_url: str | None = typer.Option(None, "--base-url", "-u", help="API base URL"),
    api_token: str | None = typer.Option(None, "--api-token", "-t", help="API token"),
) -> None:
    """Update comment for a config inside subscription."""
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
        raise typer.Exit(1)
    except Exception as e:
        formatter.show_error(e)
        raise typer.Exit(1)


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
                        title="ℹ️ No Action",
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
        raise typer.Exit(1)
    except Exception as e:
        formatter.show_error(e)
        raise typer.Exit(1)




# ═══════════════════════════════════════════════════════════════════════════
# Main Entry Point
# ═══════════════════════════════════════════════════════════════════════════


def main() -> None:
    """Main CLI entry point."""
    app()


if __name__ == "__main__":
    main()
