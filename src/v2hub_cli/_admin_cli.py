"""
Admin CLI commands for v2hub.

This module does NOT own the root Typer app.
It only registers admin subcommands into a provided Typer application.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from v2hub.core.exceptions import VPNAPIError
from v2hub.core.retry import RetryConfig

console = Console()

if TYPE_CHECKING:
    from collections.abc import Iterator

AdminClient: Any = None
try:
    from v2hub_admin import AdminClient, __version__
except ImportError:
    ADMIN_CLI_AVAILABLE = False
else:
    ADMIN_CLI_AVAILABLE = True


def short(value: str, n: int = 12) -> str:
    if n <= 3:
        return value
    return value if len(value) <= n else f"{value[: n - 1]}…"


def _fail(message: str, exit_code: int = 1) -> None:
    console.print(f"[red]{message}[/red]")
    raise typer.Exit(exit_code) from None


def _resolve_setting(
    cli_value: str | None,
    env_name: str,
) -> str | None:
    value = cli_value or os.getenv(env_name)
    if value is not None:
        value = value.strip()
    return value or None


@contextmanager
def get_admin_client(
    base_url: str | None,
    secret_key: str | None,
    timeout: float = 30.0,
) -> Iterator[AdminClient]:
    if not ADMIN_CLI_AVAILABLE:
        _fail("Error: package 'v2hub_admin' is not installed. Install it to use admin commands.")

    resolved_base_url = _resolve_setting(base_url, "V2HUB_API_URL")
    resolved_secret_key = _resolve_setting(secret_key, "V2HUB_ADMIN_SECRET")

    if not resolved_base_url:
        _fail("Error: API URL not provided. Use --base-url or V2HUB_API_URL environment variable.")

    if not resolved_secret_key:
        _fail(
            "Error: admin secret key not provided. "
            "Use --secret-key or V2HUB_ADMIN_SECRET environment variable."
        )

    client = AdminClient(
        base_url=resolved_base_url,
        secret_key=resolved_secret_key,
        timeout=timeout,
        retry_config=RetryConfig(),
    )

    try:
        yield client
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            close()


def show_error(error: Exception) -> None:
    if isinstance(error, VPNAPIError):
        console.print(
            Panel(
                f"[red]{error}[/red]\n\n"
                f"[yellow]💡 Recovery hint:[/yellow] "
                f"{getattr(error, 'recovery_hint', 'No hint available')}",
                title="❌ API Error",
                border_style="red",
            )
        )
    else:
        console.print(f"[red]Error: {error}[/red]")

    raise typer.Exit(1) from None


def key_value_table(title: str, rows: list[tuple[str, str]]) -> Table:
    table = Table(title=title, box=box.ROUNDED)
    table.add_column("Field", style="cyan", no_wrap=True)
    table.add_column("Value", style="white")

    for key, value in rows:
        table.add_row(key, value)

    return table


def register_admin_commands(admin_app: typer.Typer) -> bool:
    if not ADMIN_CLI_AVAILABLE:

        @admin_app.command("version")
        def admin_version_unavailable() -> None:
            _fail("Error: admin client is not available. Install 'v2hub_admin'.")

        return False

    @admin_app.command("version")
    def admin_version() -> None:
        console.print(
            Panel(
                f"[bold]v2hub Admin Client[/bold]\nVersion: {__version__}",
                title="ⓘ Version",
                border_style="blue",
            )
        )

    @admin_app.command("create-user")
    def create_user(
        user_id: int = typer.Argument(..., help="External user ID"),
        base_url: str | None = typer.Option(None, "--base-url", "-u", help="API base URL"),
        secret_key: str | None = typer.Option(None, "--secret-key", "-k", help="Admin secret key"),
    ) -> None:
        try:
            with get_admin_client(base_url, secret_key) as client:
                result = client.create_user(user_id)

                rows = [
                    ("User ID", str(user_id)),
                    ("API Token", str(getattr(result, "api_token", "-"))),
                ]
                if hasattr(result, "user_hash"):
                    rows.append(("User Hash", str(result.user_hash)))

                console.print(key_value_table("👤 User Created", rows))

        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(1) from None
        except Exception as e:
            show_error(e)

    @admin_app.command("get-user")
    def get_user(
        user_id: int = typer.Argument(..., help="External user ID"),
        base_url: str | None = typer.Option(None, "--base-url", "-u", help="API base URL"),
        secret_key: str | None = typer.Option(None, "--secret-key", "-k", help="Admin secret key"),
    ) -> None:
        try:
            with get_admin_client(base_url, secret_key) as client:
                result = client.get_user(user_id)

                rows = [
                    ("User ID", str(getattr(result, "user_id", user_id))),
                    ("Active", str(getattr(result, "is_active", "-"))),
                ]
                if hasattr(result, "api_token"):
                    rows.append(("API Token", str(result.api_token)))
                if hasattr(result, "user_hash"):
                    rows.append(("User Hash", str(result.user_hash)))

                console.print(key_value_table("👤 User Info", rows))

        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(1) from None
        except Exception as e:
            show_error(e)

    @admin_app.command("delete-user")
    def delete_user(
        user_id: int = typer.Argument(..., help="External user ID"),
        base_url: str | None = typer.Option(None, "--base-url", "-u", help="API base URL"),
        secret_key: str | None = typer.Option(None, "--secret-key", "-k", help="Admin secret key"),
    ) -> None:
        try:
            with get_admin_client(base_url, secret_key) as client:
                client.delete_user(user_id)

                console.print(
                    key_value_table(
                        "🗑 User Deleted",
                        [
                            ("User ID", str(user_id)),
                            ("Status", "Deleted"),
                        ],
                    )
                )

        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(1) from None
        except Exception as e:
            show_error(e)

    @admin_app.command("set-user-status")
    def set_user_status(
        user_id: int = typer.Argument(..., help="External user ID"),
        is_active: bool = typer.Option(..., "--active/--inactive", help="Set user status"),
        base_url: str | None = typer.Option(None, "--base-url", "-u", help="API base URL"),
        secret_key: str | None = typer.Option(None, "--secret-key", "-k", help="Admin secret key"),
    ) -> None:
        try:
            with get_admin_client(base_url, secret_key) as client:
                result = client.set_user_status(user_id, is_active)

                rows = [
                    ("User ID", str(getattr(result, "user_id", user_id))),
                    ("Active", str(getattr(result, "is_active", is_active))),
                ]
                if hasattr(result, "api_token"):
                    rows.append(("API Token", str(result.api_token)))
                if hasattr(result, "user_hash"):
                    rows.append(("User Hash", str(result.user_hash)))

                console.print(key_value_table("🔄 User Status Updated", rows))

        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(1) from None
        except Exception as e:
            show_error(e)

    @admin_app.command("refresh-token")
    def refresh_token(
        user_id: int = typer.Argument(..., help="User ID"),
        base_url: str | None = typer.Option(None, "--base-url", "-u", help="API base URL"),
        secret_key: str | None = typer.Option(None, "--secret-key", "-k", help="Admin secret key"),
    ) -> None:
        try:
            with get_admin_client(base_url, secret_key) as client:
                result = client.refresh_token(user_id)

                console.print(
                    key_value_table(
                        "🔑 Token Refreshed",
                        [
                            ("User ID", str(user_id)),
                            ("New token", str(getattr(result, "new_api_token", "-"))),
                        ],
                    )
                )

        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(1) from None
        except Exception as e:
            show_error(e)

    @admin_app.command("ban-ip")
    def ban_ip(
        ip_address: str = typer.Argument(..., help="IP address to ban"),
        duration_seconds: int | None = typer.Option(
            None, "--duration", "-d", help="Ban duration in seconds"
        ),
        base_url: str | None = typer.Option(None, "--base-url", "-u", help="API base URL"),
        secret_key: str | None = typer.Option(None, "--secret-key", "-k", help="Admin secret key"),
    ) -> None:
        try:
            with get_admin_client(base_url, secret_key) as client:
                result = client.ban_ip(ip_address, duration_seconds)

                console.print(
                    Panel(
                        f"[green]✓[/green] IP banned\n\n"
                        f"[bold]IP:[/bold] {ip_address}\n"
                        f"[bold]Ban ID:[/bold] {getattr(result, 'ban_id', '-')}\n"
                        f"[bold]Banned until:[/bold] {getattr(result, 'banned_until', '-')}\n"
                        f"[bold]Remaining:[/bold] {getattr(result, 'remaining_seconds', '-')}",
                        title="🚫 Ban Created",
                        border_style="red",
                    )
                )

        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(1) from None
        except Exception as e:
            show_error(e)

    @admin_app.command("unban-ip")
    def unban_ip(
        ip_address: str = typer.Argument(..., help="IP address to unban"),
        base_url: str | None = typer.Option(None, "--base-url", "-u", help="API base URL"),
        secret_key: str | None = typer.Option(None, "--secret-key", "-k", help="Admin secret key"),
    ) -> None:
        try:
            with get_admin_client(base_url, secret_key) as client:
                result = client.unban_ip(ip_address)

                console.print(
                    Panel(
                        f"[green]✓[/green] IP unbanned\n\n"
                        f"[bold]IP:[/bold] {getattr(result, 'ip_address', ip_address)}\n"
                        f"[bold]Was banned:[/bold] {getattr(result, 'was_banned', '-')}",
                        title="✅ Unban Complete",
                        border_style="green",
                    )
                )

        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(1) from None
        except Exception as e:
            show_error(e)

    @admin_app.command("ban-status")
    def ban_status(
        ip_address: str = typer.Argument(..., help="IP address to check"),
        base_url: str | None = typer.Option(None, "--base-url", "-u", help="API base URL"),
        secret_key: str | None = typer.Option(None, "--secret-key", "-k", help="Admin secret key"),
    ) -> None:
        try:
            with get_admin_client(base_url, secret_key) as client:
                status = client.get_ban_status(ip_address)

                panel_text = (
                    f"[bold]IP:[/bold] {ip_address}\n"
                    f"[bold]Is banned:[/bold] {getattr(status, 'is_banned', '-')}\n"
                    f"[bold]Banned until:[/bold] {getattr(status, 'banned_until', '-')}\n"
                    f"[bold]Remaining:[/bold] {getattr(status, 'remaining_seconds', '-')}"
                )

                console.print(
                    Panel(
                        panel_text,
                        title="📍 Ban Status",
                        border_style="yellow" if getattr(status, "is_banned", False) else "green",
                    )
                )

        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(1) from None
        except Exception as e:
            show_error(e)

    @admin_app.command("ban-list")
    def ban_list(
        base_url: str | None = typer.Option(None, "--base-url", "-u", help="API base URL"),
        secret_key: str | None = typer.Option(None, "--secret-key", "-k", help="Admin secret key"),
    ) -> None:
        try:
            with get_admin_client(base_url, secret_key) as client:
                result = client.get_ban_list()
                entries = list(getattr(result, "entries", []))
                total = int(getattr(result, "total", len(entries)))

                if not entries:
                    console.print("[yellow]No banned IPs found[/yellow]")
                    return

                table = Table(title=f"🚫 Banned IPs ({total})", box=box.ROUNDED)
                table.add_column("IP", style="cyan", no_wrap=True)
                table.add_column("Ban ID", style="white")
                table.add_column("Until", style="white")
                table.add_column("Remaining", style="white")

                for entry in entries:
                    table.add_row(
                        str(getattr(entry, "ip_address", "-")),
                        short(str(getattr(entry, "ban_id", "-"))),
                        str(getattr(entry, "banned_until", "-")),
                        str(getattr(entry, "remaining_seconds", "-")),
                    )

                console.print(table)

        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(1) from None
        except Exception as e:
            show_error(e)

    @admin_app.command("whitelist-add")
    def whitelist_add(
        ip_address: str = typer.Argument(..., help="IP or CIDR to whitelist"),
        description: str | None = typer.Option(None, "--description", "-d", help="Description"),
        base_url: str | None = typer.Option(None, "--base-url", "-u", help="API base URL"),
        secret_key: str | None = typer.Option(None, "--secret-key", "-k", help="Admin secret key"),
    ) -> None:
        try:
            with get_admin_client(base_url, secret_key) as client:
                result = client.add_to_whitelist(ip_address, description)

                console.print(
                    Panel(
                        f"[green]✓[/green] Added to whitelist\n\n"
                        f"[bold]IP/CIDR:[/bold] {ip_address}\n"
                        f"[bold]Description:[/bold] {description or '-'}\n"
                        f"[bold]Message:[/bold] {getattr(result, 'message', '-')}",
                        title="✅ Whitelist Updated",
                        border_style="green",
                    )
                )

        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(1) from None
        except Exception as e:
            show_error(e)

    @admin_app.command("whitelist-remove")
    def whitelist_remove(
        ip_address: str = typer.Argument(..., help="IP or CIDR to remove"),
        base_url: str | None = typer.Option(None, "--base-url", "-u", help="API base URL"),
        secret_key: str | None = typer.Option(None, "--secret-key", "-k", help="Admin secret key"),
    ) -> None:
        try:
            with get_admin_client(base_url, secret_key) as client:
                result = client.remove_from_whitelist(ip_address)

                console.print(
                    Panel(
                        f"[green]✓[/green] Removed from whitelist\n\n"
                        f"[bold]IP/CIDR:[/bold] {getattr(result, 'ip_address', ip_address)}\n"
                        f"[bold]Was whitelisted:[/bold] {getattr(result, 'was_whitelisted', '-')}",
                        title="✅ Whitelist Updated",
                        border_style="green",
                    )
                )

        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(1) from None
        except Exception as e:
            show_error(e)

    @admin_app.command("whitelist-list")
    def whitelist_list(
        base_url: str | None = typer.Option(None, "--base-url", "-u", help="API base URL"),
        secret_key: str | None = typer.Option(None, "--secret-key", "-k", help="Admin secret key"),
    ) -> None:
        try:
            with get_admin_client(base_url, secret_key) as client:
                result = client.list_whitelist()
                entries = list(getattr(result, "entries", []))
                total = int(getattr(result, "total", len(entries)))

                if not entries:
                    console.print("[yellow]No whitelist entries found[/yellow]")
                    return

                table = Table(title=f"✅ Whitelist ({total})", box=box.ROUNDED)
                table.add_column("IP/CIDR", style="cyan", no_wrap=True)
                table.add_column("Description", style="white")

                for entry in entries:
                    table.add_row(
                        str(getattr(entry, "ip_address", "-")),
                        str(getattr(entry, "description", "-")),
                    )

                console.print(table)

        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(1) from None
        except Exception as e:
            show_error(e)

    return True
