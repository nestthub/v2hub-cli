"""
Output formatting utilities for CLI.

Provides consistent, beautiful console output using rich.
"""

from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING, Any, Protocol

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
else:
    Subscription = Any

__all__ = ["OutputFormatter"]


class HasBanEntry(Protocol):
    ip_address: Any
    banned_until: Any
    remaining_seconds: Any


class HasWhitelistEntry(Protocol):
    ip_address: Any
    description: Any
    added_at: Any


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
        table = Table(title=title, box=box.ROUNDED)
        table.add_column("Name", style="cyan")
        table.add_column("Token", style="green")
        table.add_column("Sources", justify="right", style="yellow")
        table.add_column("Description", style="white")

        for sub in subscriptions:
            table.add_row(
                self._safe_str(getattr(sub, "name", None)),
                self._safe_str(getattr(sub, "token", None)),
                self._safe_str(getattr(sub, "sources_count", None)),
                self._safe_str(getattr(sub, "description", None)),
            )

        return table

    def create_ban_table(
        self,
        bans: Sequence[HasBanEntry],
        *,
        total: int | None = None,
    ) -> Table:
        """
        Create formatted ban list table.

        Args:
            bans: List of ban entries
            total: Total count for title

        Returns:
            Configured rich Table
        """

        title = f"🚫 Bans ({total})" if total is not None else "🚫 Bans"

        table = Table(title=title, box=box.ROUNDED)
        table.add_column("IP", style="cyan")
        table.add_column("Until", style="yellow")
        table.add_column("Remaining", justify="right", style="green")

        for ban in bans:
            table.add_row(
                self._safe_str(getattr(ban, "ip_address", None)),
                self._safe_str(getattr(ban, "banned_until", None)),
                self._safe_str(getattr(ban, "remaining_seconds", None)),
            )

        return table

    def create_whitelist_table(
        self,
        entries: Sequence[HasWhitelistEntry],
        *,
        total: int | None = None,
    ) -> Table:
        """
        Create formatted whitelist table.

        Args:
            entries: List of whitelist entries
            total: Total count for title

        Returns:
            Configured rich Table
        """

        title = f"✅ Whitelist ({total})" if total is not None else "✅ Whitelist"

        table = Table(title=title, box=box.ROUNDED)
        table.add_column("IP/CIDR", style="cyan")
        table.add_column("Description", style="white")
        table.add_column("Added At", style="yellow")

        for entry in entries:
            table.add_row(
                self._safe_str(getattr(entry, "ip_address", None)),
                self._safe_str(getattr(entry, "description", None)),
                self._safe_str(getattr(entry, "added_at", None)),
            )

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

    def show_subscription_detail(self, subscription: Subscription) -> None:
        """
        Display detailed subscription information.

        Args:
            subscription: Subscription to display
        """

        self.console.print(
            Panel(
                f"[bold cyan]{getattr(subscription, 'name', '-')}[/bold cyan]\n"
                f"Token: [green]{getattr(subscription, 'token', '-')}[/green]\n"
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
