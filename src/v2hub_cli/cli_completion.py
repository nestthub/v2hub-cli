"""
Dynamic shell-completion helpers.

Shell completion runs the CLI process on every `<TAB>` press, so anything
done here has to be fast and must never raise: a slow or crashing
completion function makes the *shell itself* feel broken, not just the
completion. Every function in this module therefore:

- uses a short, fixed timeout and zero retries for any network call
  (the normal `VPNClient`/`AdminClient` defaults -- up to 3 retries with
  backoff up to 60s -- are appropriate for real commands, not for a
  keystroke)
- resolves credentials the same way the real commands do (already-typed
  `--base-url`/`--api-token`/`--secret-key` on the command line, then the
  `V2HUB_API_URL` / `V2HUB_API_TOKEN` / `V2HUB_ADMIN_SECRET` env vars),
  reading already-typed values from `ctx.params` / `ctx.parent.params`
- swallows every exception and falls back to "no suggestions" rather
  than ever letting an error surface into the completion machinery

Nothing here is imported eagerly by modules that don't need it, and the
network/client imports are deferred into each function so that importing
this module (which happens on every CLI invocation, including ones with
no completion involved) stays cheap.

Completion callbacks are written against Click's `shell_complete(ctx,
param, incomplete)` signature. Typer additionally exposes a higher-level
`autocompletion(ctx, args, incomplete)` parameter, but as of the Typer
version this project pins, `shell_complete` is still the fully
functional option (only `autocompletion` gets Typer's own Rich-flavored
help rendering) -- it's marked for eventual removal, but there's no
replacement with equivalent capability yet, and this module only calls
into stable Click APIs, so it does not depend on Typer internals beyond
that parameter name.
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterator

    # Typer's `Argument(shell_complete=...)` type-checks the callback
    # against `typer._click.core.Context`/`Parameter` -- Typer's own
    # vendored copy of Click's classes, not the standalone `click`
    # package's. The two are structurally compatible (duck typing means
    # this is a non-issue at runtime), but they are *different classes*
    # as far as mypy is concerned, so annotating against the real
    # `click` package here would make every `shell_complete=` wiring in
    # cli.py/_admin_cli.py fail type-checking with an "incompatible
    # type" error, even though the code runs correctly. Importing from
    # `typer._click` matches what Typer itself expects
    # (`typer.models.ParameterInfo.shell_complete`'s declared type is
    # `Callable[[_click.Context, _click.Parameter, str],
    # list[CompletionItem] | list[str]]`).
    from typer._click.core import Context, Parameter
    from typer._click.shell_completion import CompletionItem

# Keep this small: it bounds the worst case added latency of a single
# <TAB> press when the API is unreachable or slow.
COMPLETION_TIMEOUT_SECONDS = 2.0


@contextmanager
def _quiet_client_logging() -> Iterator[None]:
    """
    Suppress the v2hub/v2hub_admin clients' own error-level logging
    (e.g. "Network error: GET /api/v1/subs") for the duration of a
    completion request.

    Those clients log through per-module loggers (e.g.
    `v2hub.http.client`) which by default write to stderr -- fine for a
    real command failing, but exactly the kind of noise that shouldn't
    appear above the prompt just because a `<TAB>` press happened to hit
    an unreachable API. We already surface failures by returning no
    suggestions, so nothing is lost by staying quiet here.

    `logging.disable(level)` is used rather than toggling individual
    loggers' `.disabled` flags: that flag only short-circuits the exact
    logger it's set on, not descendants reached by dotted module name
    (`v2hub.http.client` is unaffected by disabling `v2hub`), so
    silencing every current and future logger the client libraries might
    use would mean guessing all their internal module names. The global
    disable applies process-wide for CRITICAL-and-below regardless of
    logger name, and is restored to its previous threshold immediately
    after.
    """
    previous_level = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        yield
    finally:
        logging.disable(previous_level)


def _env(name: str) -> str | None:
    value = os.getenv(name)
    if value is not None:
        value = value.strip()
    return value or None


def _typed_value(ctx: Context, name: str) -> str | None:
    """
    Look up an option's already-typed value anywhere in the current
    command chain (the command itself, or a parent group such as
    `v2hub provider <user_id>`).
    """
    node: Context | None = ctx
    while node is not None:
        value = node.params.get(name)
        if value:
            return str(value)
        node = node.parent
    return None


def _resolve_base_url(ctx: Context) -> str | None:
    return _typed_value(ctx, "base_url") or _env("V2HUB_API_URL")


def _resolve_api_token(ctx: Context) -> str | None:
    return _typed_value(ctx, "api_token") or _env("V2HUB_API_TOKEN")


def _resolve_secret_key(ctx: Context) -> str | None:
    return _typed_value(ctx, "secret_key") or _env("V2HUB_ADMIN_SECRET")


def _resolve_provider_user_id(ctx: Context) -> int | None:
    """Read the `user_id` captured by `v2hub provider {user_id} ...`."""
    raw = _typed_value(ctx, "user_id")
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _filtered(values: list[str], incomplete: str) -> list[str]:
    if not incomplete:
        return values
    return [v for v in values if v.startswith(incomplete)]


def _completion_item_class() -> type[Any] | None:
    """
    Resolve the `CompletionItem` class the running Typer install will
    actually recognize.

    This project depends on `typer`, not on `click` directly -- and as
    of Typer 0.16+, Typer vendors its own copy of Click under
    `typer._click` rather than requiring the separately-installed
    `click` package at all. An environment with only `typer` installed
    (no top-level `click`) is entirely normal and supported, so
    importing `click.shell_completion` unconditionally breaks completion
    for exactly the users this feature is meant to help.

    We prefer the real `click` package when it happens to be present
    (e.g. pulled in by some other dependency, or an older Typer that
    still requires it) since it's the publicly documented, stable
    import path. Otherwise we fall back to Typer's vendored copy, which
    is what `typer._click.core.Parameter.shell_complete` actually
    type-checks the returned items against at runtime -- so this is not
    a lesser fallback, it's the class Typer itself expects.
    """
    try:
        from click.shell_completion import CompletionItem as ClickCompletionItem
    except ImportError:
        pass
    else:
        return ClickCompletionItem

    try:
        from typer._click.shell_completion import (
            CompletionItem as TyperClickCompletionItem,
        )
    except ImportError:
        return None
    else:
        return TyperClickCompletionItem


def _completion_items(pairs: list[tuple[str, str | None]], incomplete: str) -> list[Any]:
    """
    Turn `(value, hint)` pairs into completion items, filtered by the
    already-typed prefix.

    The hint is shown alongside the value in shells that support it
    (zsh's `_describe`, fish's tab-separated description column); bash
    has no equivalent mechanism and only ever shows the value itself --
    that's a limitation of bash completion, not something this CLI can
    work around. Either way, the value inserted on selection is always
    just `value`, never the hint.

    If no `CompletionItem` implementation can be found at all (not
    expected, but see `_completion_item_class`), falls back to plain
    value strings -- completion still works, just without hints, rather
    than the whole command blowing up.
    """
    filtered = [
        (value, hint) for value, hint in pairs if not incomplete or value.startswith(incomplete)
    ]

    item_cls = _completion_item_class()
    if item_cls is None:
        return [value for value, _hint in filtered]

    return [item_cls(value, help=hint) for value, hint in filtered]


def _no_retry_kwargs() -> dict[str, Any]:
    from v2hub.core.retry import RetryConfig

    return {
        "timeout": COMPLETION_TIMEOUT_SECONDS,
        "retry_config": RetryConfig(max_retries=0),
    }


# ─────────────────────── Subscription tokens ───────────────────────


def complete_subscription_token(
    ctx: Context, _param: Parameter, incomplete: str
) -> list[CompletionItem] | list[str]:
    """
    Suggest subscription tokens by calling `list_subscriptions()`.

    Each suggestion carries the subscription's name as a hint, shown as
    "{token} {name}" in shells that support it (see `_completion_items`)
    -- but only the token itself is ever inserted on selection.

    Used for the self-service `token` argument (`v2hub get`,
    `v2hub add-sources`, `v2hub update`, ...) and, via
    `complete_provider_subscription_token`, for the equivalent
    `v2hub provider {user_id} ...` commands.
    """
    as_provider_for_user_id = _resolve_provider_user_id(ctx)
    return _list_subscription_tokens(ctx, incomplete, as_provider_for_user_id)


def complete_provider_subscription_token(
    ctx: Context, param: Parameter, incomplete: str
) -> list[CompletionItem] | list[str]:
    return complete_subscription_token(ctx, param, incomplete)


def _list_subscription_tokens(
    ctx: Context, incomplete: str, as_provider_for_user_id: int | None
) -> list[Any]:
    base_url = _resolve_base_url(ctx)
    api_token = _resolve_api_token(ctx)
    if not base_url or not api_token:
        return []

    try:
        from v2hub.client import VPNClient

        with (
            _quiet_client_logging(),
            VPNClient(base_url, api_token, **_no_retry_kwargs()) as client,
        ):
            subs = client.list_subscriptions(as_provider_for_user_id=as_provider_for_user_id)
    except Exception:
        return []

    pairs = [(s.token, getattr(s, "name", None) or None) for s in subs]
    return _completion_items(pairs, incomplete)


# ─────────────────────── Config hashes within a subscription ───────────────────────

# Cap for the hint shown next to an external_url/internal_token config's
# raw data -- long enough to be useful, short enough not to blow out the
# completion menu width.
_SOURCE_HINT_MAX_LENGTH = 70


def _short(text: str, max_length: int) -> str:
    if max_length <= 1 or len(text) <= max_length:
        return text
    return f"{text[: max_length - 1]}…"


def _source_hint(source: Any) -> str | None:
    """
    Build the "{source}" half of a config-hash completion's
    "{config_hash} {source}" display.

    - `external_url` / `internal_token` sources: their raw `data` (a URL
      or token), truncated to `_SOURCE_HINT_MAX_LENGTH` chars so one
      long token doesn't dominate the completion menu.
    - `config` sources: just the comment, i.e. the part of the `data`
      URI after the first `#` (v2ray/vless/vmess/trojan links carry a
      human-readable remark there) -- not the config body itself, since
      showing the full connection string next to every entry would
      swamp the useful part (the remark) in noise. If there's no `#`
      (no remark set), no hint is shown rather than dumping the raw
      config string.
    """
    from v2hub.models import SourceType

    data = getattr(source, "data", None)
    if not data:
        return None

    source_type = getattr(source, "source_type", None)

    if source_type == SourceType.CONFIG:
        _prefix, sep, comment = data.partition("#")
        if not sep or not comment:
            return None
        return _short(comment, _SOURCE_HINT_MAX_LENGTH)

    # external_url, internal_token, and any future source type: show the
    # data itself, truncated.
    return _short(data, _SOURCE_HINT_MAX_LENGTH)


def complete_config_hash(
    ctx: Context, _param: Parameter, incomplete: str
) -> list[CompletionItem] | list[str]:
    """
    Suggest config/source hashes for `--config-id` on `update-config`.

    Each suggestion carries a hint built by `_source_hint` -- the config's
    comment for `config` sources, or a truncated view of the raw
    URL/token otherwise -- shown as "{config_hash} {source}" in shells
    that support it, though only the hash is ever inserted.

    Requires the `token` argument to already be typed on the command
    line (it's positional and comes before `--config-id`), since a
    subscription's configs can only be listed by its token.
    """
    token = _typed_value(ctx, "token")
    if not token:
        return []

    base_url = _resolve_base_url(ctx)
    api_token = _resolve_api_token(ctx)
    if not base_url or not api_token:
        return []

    as_provider_for_user_id = _resolve_provider_user_id(ctx)

    try:
        from v2hub.client import VPNClient

        with (
            _quiet_client_logging(),
            VPNClient(base_url, api_token, **_no_retry_kwargs()) as client,
        ):
            sub = client.get_subscription(token, as_provider_for_user_id=as_provider_for_user_id)
    except Exception:
        return []

    pairs = [(str(source.id), _source_hint(source)) for source in sub.sources]
    return _completion_items(pairs, incomplete)


# Older name, kept as an alias: the argument is `--config-id` in the CLI
# and `id` on the `Source` model, so both names describe the same thing.
complete_config_id = complete_config_hash


# ─────────────────────── Admin: providers ───────────────────────


def complete_provider_hash(ctx: Context, _param: Parameter, incomplete: str) -> list[str]:
    base_url = _resolve_base_url(ctx)
    secret_key = _resolve_secret_key(ctx)
    if not base_url or not secret_key:
        return []

    try:
        from v2hub_admin import AdminClient

        with (
            _quiet_client_logging(),
            AdminClient(base_url=base_url, secret_key=secret_key, **_no_retry_kwargs()) as client,
        ):
            result = client.get_providers()
    except Exception:
        return []

    hashes = [str(h) for h in getattr(result, "provider_hashes", {}).values()]
    return _filtered(hashes, incomplete)


# ─────────────────────── Admin: IP addresses (bans / whitelist) ───────────────────────


def complete_banned_ip(ctx: Context, _param: Parameter, incomplete: str) -> list[str]:
    base_url = _resolve_base_url(ctx)
    secret_key = _resolve_secret_key(ctx)
    if not base_url or not secret_key:
        return []

    try:
        from v2hub_admin import AdminClient

        with (
            _quiet_client_logging(),
            AdminClient(base_url=base_url, secret_key=secret_key, **_no_retry_kwargs()) as client,
        ):
            result = client.get_ban_list()
    except Exception:
        return []

    ips = [str(getattr(entry, "ip_address", "")) for entry in getattr(result, "entries", [])]
    return _filtered([ip for ip in ips if ip], incomplete)


def complete_whitelisted_ip(ctx: Context, _param: Parameter, incomplete: str) -> list[str]:
    base_url = _resolve_base_url(ctx)
    secret_key = _resolve_secret_key(ctx)
    if not base_url or not secret_key:
        return []

    try:
        from v2hub_admin import AdminClient

        with (
            _quiet_client_logging(),
            AdminClient(base_url=base_url, secret_key=secret_key, **_no_retry_kwargs()) as client,
        ):
            result = client.list_whitelist()
    except Exception:
        return []

    ips = [str(getattr(entry, "ip_address", "")) for entry in getattr(result, "entries", [])]
    return _filtered([ip for ip in ips if ip], incomplete)
