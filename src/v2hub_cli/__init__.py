from __future__ import annotations

from importlib.metadata import PackageNotFoundError, metadata, version

try:
    __version__ = version("v2hub-cli")
    __author__ = metadata("v2hub-cli")["Author-email"]
except PackageNotFoundError:
    __version__ = "unknown"
    __author__ = "unknown"

__api_version__ = "v1"
