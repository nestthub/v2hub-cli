"""
Output formatting utilities for CLI.

Provides consistent, beautiful console output using rich.
"""

from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING, Any

try:
    from rich import box
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
except ImportError as exc:
    raise ImportError(
        "CLI dependencies not installed. Install with: pip install v2hub[cli]"
    ) from exc

from v2hub.core.exceptions import VPNAPIError
from v2hub.models import SourceType

if TYPE_CHECKING:
    from collections.abc import Sequence

    from v2hub.models import Subscription

__all__ = ["OutputFormatter"]


class OutputFormatter:
    """
    Formats CLI output with rich styling.

    Centralizes all console output formatting for consistency
    and maintainability.
    """

    def __init__(self, console: Console | None = None) -> None:
        """
        Initialize formatter.

        Args:
            console: Optional rich console instance. Creates new if None.
        """
        self.console = console or Console()

    @staticmethod
    def short(text: str, max_length: int = 12) -> str:
        """
        Shorten text with ellipsis if too long.

        Args:
            text: Text to potentially shorten
            max_length: Maximum allowed length

        Returns:
            Original or shortened text with ellipsis
        """
        if max_length <= 3:
            return text
        return text if len(text) <= max_length else f"{text[: max_length - 3]}…"

    @staticmethod
    def _safe_str(value: Any, default: str = "-") -> str:
        if value is None:
            return default
        return str(value)

    def show_error(self, error: Exception) -> None:
        """
        Display formatted error message.

        Args:
            error: Exception to display
        """
        if isinstance(error, VPNAPIError):
            self.console.print(
                Panel(
                    f"[red]{error}[/red]\n\n"
                    f"[yellow]💡 Recovery hint:[/yellow] "
                    f"{getattr(error, 'recovery_hint', 'No hint available')}",
                    title="❌ API Error",
                    border_style="red",
                )
            )
            return

        self.console.print(f"[red]Error: {error}[/red]")

    def show_missing_config(self, missing: str) -> None:
        """
        Display missing configuration error.

        Args:
            missing: Description of what's missing
        """
        self.console.print(f"[red]Error: {missing}[/red]")

    def show_success(
        self,
        message: str,
        *,
        title: str = "✅ Success",
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Display success message with optional details.

        Args:
            message: Main success message
            title: Panel title
            details: Optional key-value details to display
        """

        content = f"[green]✓[/green] {message}"

        if details:
            details_text = "\n".join(
                f"[bold]{key}:[/bold] {value}" for key, value in details.items()
            )
            content = f"{content}\n\n{details_text}"

        self.console.print(Panel(content, title=title, border_style="green"))

    def create_subscription_table(
        self,
        subscriptions: Sequence[Subscription],
        *,
        title: str = "📋 Subscriptions",
    ) -> Table:
        """
        Create formatted subscription list table.

        Args:
            subscriptions: List of subscriptions
            title: Table title

        Returns:
            Configured rich Table
        """
        show_provider_column = any(getattr(sub, "provider_name", None) for sub in subscriptions)

        table = Table(title=title, box=box.ROUNDED)
        table.add_column("Name", style="cyan")
        table.add_column("Token", style="green")
        table.add_column("Configs", justify="right", style="yellow")
        table.add_column("Description", style="white")
        if show_provider_column:
            table.add_column("Provider", style="magenta")

        for sub in subscriptions:
            row = [
                self._safe_str(getattr(sub, "name", None)),
                self._safe_str(getattr(sub, "token", None)),
                self._safe_str(getattr(sub, "sources_count", None)),
                self._safe_str(getattr(sub, "description", None)),
            ]
            if show_provider_column:
                row.append(self._safe_str(getattr(sub, "provider_name", None)))
            table.add_row(*row)

        return table

    def show_version(self, versions: dict[str, str]) -> None:
        """
        Display installed package versions.

        Args:
            versions: Mapping of package names to version strings.
        """
        body = "\n".join(
            f"[cyan]{name}[/cyan]: [green]{version}[/green]" for name, version in versions.items()
        )

        self.console.print(
            Panel(
                body,
                title="ⓘ Versions",
                border_style="cyan",
            )
        )

    def show_provider_connection(
        self,
        connection: Any,
        *,
        title: str = "🔗 Connection",
    ) -> None:
        """
        Display a provider connection's status and connection link.
        """
        status = getattr(connection, "status", None)
        status_str = getattr(status, "value", status)

        style = {
            "approved": "green",
            "revoked": "red",
        }.get(str(status_str), "yellow")

        user_id = self._safe_str(getattr(connection, "user_id", None))

        lines = [
            f"User ID: [cyan]{user_id}[/cyan]",
            f"Status: [{style}]{self._safe_str(status_str)}[/{style}]",
        ]

        connection_link = getattr(connection, "connection_link", None)

        if connection_link:
            lines.append(f"Connection link: [link={connection_link}]{connection_link}[/link]")

        self.console.print(
            Panel(
                "\n".join(lines),
                title=title,
                border_style=style,
            )
        )

    def show_me(self, me: Any) -> None:
        """
        Display the currently authenticated user's own account info.

        Args:
            me: A MeResponse-like object with `user_id` and `is_active`.
        """
        is_active = getattr(me, "is_active", None)
        style = "green" if is_active else "red"

        self.console.print(
            Panel(
                f"User ID: [cyan]{self._safe_str(getattr(me, 'user_id', None))}[/cyan]\n"
                f"Active: [{style}]{self._safe_str(is_active)}[/{style}]",
                title="👤 Me",
                border_style="cyan",
            )
        )

    def show_connection(self, connection: Any, *, title: str = "🔗 Connection") -> None:
        """
        Display a single connection between the current user and a provider.

        Args:
            connection: A ConnectionResponse-like object with
                `provider_name`, `provider_url`, `is_authorized`, `status`.
            title: Panel title.
        """
        status = getattr(connection, "status", None)
        status_str = getattr(status, "value", status)

        style = {
            "approved": "green",
            "revoked": "red",
            "pending": "yellow",
        }.get(str(status_str), "white")

        is_authorized = getattr(connection, "is_authorized", False)
        authorized_style = "green" if is_authorized else "red"

        provider_url = getattr(connection, "provider_url", None)
        url_line = f"URL: {provider_url}\n" if provider_url else ""

        self.console.print(
            Panel(
                f"Provider: [cyan]{self._safe_str(getattr(connection, 'provider_name', None))}[/cyan]\n"
                f"{url_line}"
                f"Authorized: [{authorized_style}]{self._safe_str(is_authorized)}[/{authorized_style}]\n"
                f"Status: [{style}]{self._safe_str(status_str)}[/{style}]",
                title=title,
                border_style=style,
            )
        )

    def show_connections_table(
        self,
        connections: Sequence[Any],
        *,
        title: str = "🔗 Connections",
    ) -> None:
        """
        Display the current user's provider connections as a table.

        Args:
            connections: Sequence of ConnectionResponse-like objects.
            title: Table title.
        """
        if not connections:
            self.console.print("[yellow]No provider connections found[/yellow]")
            return

        table = Table(title=f"{title} ({len(connections)})", box=box.ROUNDED)
        table.add_column("Provider", style="cyan")
        table.add_column("URL", style="white")
        table.add_column("Authorized", justify="center", style="green")
        table.add_column("Status", style="yellow")

        for conn in connections:
            status = getattr(conn, "status", None)
            status_str = getattr(status, "value", status)
            is_authorized = getattr(conn, "is_authorized", False)

            table.add_row(
                self._safe_str(getattr(conn, "provider_name", None)),
                self._safe_str(getattr(conn, "provider_url", None)),
                "✓" if is_authorized else "✗",
                self._safe_str(status_str),
            )

        self.console.print(table)

    def show_public_subscription(self, subscription: Any, *, decode: bool = False) -> None:
        """
        Display a public subscription's configs.

        Args:
            subscription: A PublicSubscriptionResponse-like object with a
                `content` (base64) field and, when the real model is
                passed, `decode()`/`get_configs()`/`config_count` helpers.
            decode: If True and the object supports it, print the decoded
                configs (one per line) instead of the raw base64 content.
        """
        title = self._safe_str(getattr(subscription, "title", None), default="v2hub")

        if decode and hasattr(subscription, "get_configs"):
            configs = subscription.get_configs()
            body = "\n".join(configs) if configs else "[yellow](no configs)[/yellow]"
            count = len(configs)
            self.console.print(
                Panel(
                    body,
                    title=f"📡 {title} ({count} config{'s' if count != 1 else ''})",
                    border_style="cyan",
                )
            )
            return

        content = self._safe_str(getattr(subscription, "content", None))
        self.console.print(
            Panel(
                content,
                title=f"📦 {title} (base64)",
                border_style="cyan",
            )
        )

    def show_subscription_detail(self, subscription: Subscription) -> None:
        """
        Display detailed subscription information.

        Args:
            subscription: Subscription to display
        """

        provider_name = getattr(subscription, "provider_name", None)
        provider_line = f"Provider: [magenta]{provider_name}[/magenta]\n" if provider_name else ""

        self.console.print(
            Panel(
                f"[bold cyan]{getattr(subscription, 'name', '-')}[/bold cyan]\n"
                f"Token: [green]{getattr(subscription, 'token', '-')}[/green]\n"
                f"{provider_line}"
                f"Description: {getattr(subscription, 'description', '-') or '-'}\n"
                f"Total configs: [yellow]{getattr(subscription, 'sources_count', '-')}[/yellow]\n"
                f"Created: {getattr(subscription, 'created_at', '-')}\n"
                f"Updated: {getattr(subscription, 'updated_at', '-')}",
                title="📦 Subscription",
                border_style="cyan",
            )
        )

        sources = getattr(subscription, "sources", None)
        if not sources:
            return

        table = Table(title="📡 Sources", box=box.ROUNDED)
        table.add_column("ID", style="green")
        table.add_column("Type", style="cyan")
        table.add_column("Data", style="white")
        table.add_column("Visible", justify="center", style="green")
        table.add_column("Depth", justify="right", style="blue")
        table.add_column("Order", justify="right", style="yellow")

        for source in sources:
            data = self._safe_str(getattr(source, "data", None))
            source_type = getattr(source, "source_type", None)

            if source_type == SourceType.CONFIG and data:
                conf_parts = data.split("#", maxsplit=1)
                if len(conf_parts) == 2:
                    comment = conf_parts[1]
                    data = f"{conf_parts[0]}#{self.short(comment, 32)}"
                    data = "\n".join(textwrap.wrap(data, width=180))

            visible = "✓" if not getattr(source, "is_hidden", False) else "✗"

            table.add_row(
                self._safe_str(getattr(source, "id", None)),
                self._safe_str(source_type),
                data,
                visible,
                self._safe_str(getattr(source, "max_depth", None)),
                self._safe_str(getattr(source, "order_index", None)),
            )

        self.console.print(table)
