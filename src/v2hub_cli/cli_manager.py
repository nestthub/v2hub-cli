"""
Client management for CLI.

Handles initialization and lifecycle of API clients.
"""

from __future__ import annotations

"""
Client management for CLI.

Handles initialization and lifecycle of API clients.
"""

import os
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Iterator

__all__ = ["ClientManager"]

if TYPE_CHECKING:
    from v2hub.client import VPNClient
    from v2hub_admin.client import AdminClient
else:
    VPNClient = Any
    AdminClient = Any


class ClientManager:
    """
    Manages API client lifecycle.

    Centralizes client creation, configuration resolution,
    and environment variable handling.
    """

    V2HUB_API_URL = "V2HUB_API_URL"
    V2HUB_API_TOKEN = "V2HUB_API_TOKEN"
    V2HUB_ADMIN_SECRET = "V2HUB_ADMIN_SECRET"

    @staticmethod
    def _env(name: str) -> str | None:
        value = os.getenv(name)
        if value is not None:
            value = value.strip()
        return value or None

    @classmethod
    def resolve_base_url(cls, base_url: str | None = None) -> str | None:
        return (base_url or cls._env(cls.V2HUB_API_URL))

    @classmethod
    def resolve_api_token(cls, api_token: str | None = None) -> str | None:
        return (api_token or cls._env(cls.V2HUB_API_TOKEN))

    @classmethod
    def resolve_secret_key(cls, secret_key: str | None = None) -> str | None:
        return (secret_key or cls._env(cls.V2HUB_ADMIN_SECRET))

    @staticmethod
    @contextmanager
    def get_client(
        base_url: str | None = None,
        api_token: str | None = None,
    ) -> Iterator[VPNClient]:
        from v2hub.client import VPNClient

        resolved_base_url = ClientManager.resolve_base_url(base_url)
        resolved_api_token = ClientManager.resolve_api_token(api_token)

        if not resolved_base_url:
            raise ValueError(
                f"API URL not provided. Use --base-url or {ClientManager.V2HUB_API_URL} env var"
            )

        if not resolved_api_token:
            raise ValueError(
                f"API token not provided. Use --api-token or {ClientManager.V2HUB_API_TOKEN} env var"
            )

        with VPNClient(resolved_base_url, resolved_api_token) as client:
            yield client

    @staticmethod
    @contextmanager
    def get_admin_client(
        base_url: str | None = None,
        secret_key: str | None = None,
        timeout: float = 30.0,
    ) -> Iterator[AdminClient]:
        try:
            from v2hub_admin.client import AdminClient
        except ImportError as exc:
            raise ImportError(
                "Admin CLI support is not installed. "
                "Install v2hub-admin or use the admin extra."
            ) from exc

        from v2hub.core.retry import RetryConfig

        resolved_base_url = ClientManager.resolve_base_url(base_url)
        resolved_secret_key = ClientManager.resolve_secret_key(secret_key)

        if not resolved_base_url:
            raise ValueError(
                f"API URL not provided. Use --base-url or {ClientManager.V2HUB_API_URL} env var"
            )

        if not resolved_secret_key:
            raise ValueError(
                f"Admin secret key not provided. Use --secret-key or {ClientManager.V2HUB_ADMIN_SECRET} env var"
            )

        with AdminClient(
            base_url=resolved_base_url,
            secret_key=resolved_secret_key,
            timeout=timeout,
            retry_config=RetryConfig(),
        ) as client:
            yield client
