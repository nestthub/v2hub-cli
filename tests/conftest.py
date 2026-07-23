from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from v2hub.client import VPNClient
from v2hub.core.exceptions import VPNAPIError
from v2hub.models.requests import SourceCreate


@pytest.fixture
def fake_source_create() -> type[SourceCreate]:
    """Return real SourceCreate model."""
    return SourceCreate


@pytest.fixture
def fake_vpn_api_error() -> type[VPNAPIError]:
    """Return real VPNAPIError class."""
    return VPNAPIError


@pytest.fixture
def mock_vpn_client() -> MagicMock:
    """Mock VPNClient usable as context manager."""
    client = MagicMock(spec=VPNClient, name="VPNClient")
    client.__enter__ = MagicMock(return_value=client)
    client.__exit__ = MagicMock(return_value=False)
    return client


@pytest.fixture
def make_subscription() -> Any:
    """Factory for subscription-like objects."""

    def _make(
        *,
        name: str = "my-sub",
        token: str = "tok_123",
        description: str | None = "desc",
        sources_count: int = 2,
        created_at: str = "2026-01-01T00:00:00Z",
        updated_at: str = "2026-01-02T00:00:00Z",
        sources: list[Any] | None = None,
    ) -> Any:
        return type(
            "SubscriptionStub",
            (),
            {
                "name": name,
                "token": token,
                "description": description,
                "sources_count": sources_count,
                "created_at": created_at,
                "updated_at": updated_at,
                "sources": sources if sources is not None else [],
            },
        )()

    return _make
