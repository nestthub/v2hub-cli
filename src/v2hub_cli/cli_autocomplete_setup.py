"""
Automatic shell-completion installation.

Typer/Click already know how to install a completion script for the
user's shell (`v2hub --install-completion`); this module just calls that
same installer on the user's behalf, once, so nobody has to know the flag
exists in the first place -- matching how a lot of modern CLIs (e.g.
`gh`) quietly wire up completion the first time they run in a real
terminal.

Design constraints, and why:

- **Runs at most once per (CLI version, shell).** A marker file records
  what's already been installed. Re-running the installer on every
  invocation would mean touching the user's rc file on every command,
  which is invasive and pointless; re-running it once per upgrade means
  a newer completion script (new commands, new dynamic completions)
  still gets picked up over time.
- **Never runs during actual shell completion.** Click/Typer invoke this
  same executable with `_V2HUB_COMPLETE` set in the environment to
  answer a `<TAB>` press. That path must stay minimal and fast; it must
  never recurse into installing anything.
- **Only runs for an interactive terminal session.** Scripts, CI,
  cron, and `subprocess` invocations should never have their
  environment mutated as a side effect of running this CLI. We check
  `sys.stdin.isatty()` (and that stdin/stdout are attached to a real
  terminal at all) before doing anything.
- **Never touches config for a shell we can't confidently detect and
  support.** We rely on the same shell-detection Typer's own
  `--install-completion` uses (`shellingham`, which inspects the parent
  process tree rather than trusting a possibly-stale `$SHELL`), and only
  proceed for bash/zsh/fish -- the shells Typer knows how to wire up
  without any further prompting. PowerShell is skipped: it needs a
  profile-script decision Typer can't make silently.
- **Completely silent on failure.** No permissions to write the rc file,
  an exotic environment, a sandboxed container, whatever -- if
  installation fails for any reason, the user's actual command must
  still run normally, with no error, no traceback, no noise. The only
  output this module ever produces is a single one-line notice the
  *first* time installation succeeds.
- **Respects an explicit opt-out.** `V2HUB_NO_AUTOCOMPLETE=1` (or `0`
  disables/enables respectively, matching common CLI conventions)
  skips this entirely, for anyone who manages their dotfiles some other
  way (chezmoi, nix, a custom completion setup, etc.) and doesn't want
  this CLI editing them.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Bumping this forces re-installation for everyone on upgrade, e.g. if
# the completion script format or the set of dynamic completions changes
# in a way worth picking up automatically. Independent of the package
# version so it only needs to change when this file's behavior does.
_COMPLETION_SETUP_REVISION = "1"

_SUPPORTED_SHELLS = {"bash", "zsh", "fish"}


def _state_dir() -> Path:
    base = os.getenv("XDG_STATE_HOME") or os.getenv("XDG_CACHE_HOME")
    if base:
        return Path(base) / "v2hub-cli"
    return Path.home() / ".cache" / "v2hub-cli"


def _marker_path(shell: str) -> Path:
    return _state_dir() / f"completion-installed-{shell}-{_COMPLETION_SETUP_REVISION}"


def _opted_out() -> bool:
    value = os.getenv("V2HUB_NO_AUTOCOMPLETE", "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _is_interactive_terminal() -> bool:
    try:
        return sys.stdin.isatty() and sys.stdout.isatty()
    except Exception:
        return False


def _already_running_as_completion() -> bool:
    # Click/Typer set this to answer a <TAB> press; never do setup work
    # on that hot path.
    return any(k.endswith("_COMPLETE") for k in os.environ)


def maybe_install_completion() -> None:
    """
    Best-effort, silent-on-failure, install-once shell completion setup.

    Safe to call unconditionally at the top of `main()`: every early-exit
    condition below is cheap, and the whole thing is wrapped so that no
    exception here can ever prevent the real CLI command from running.
    """
    try:
        _maybe_install_completion_impl()
    except Exception:
        # Never let completion setup break the actual command.
        return


def _maybe_install_completion_impl() -> None:
    if _already_running_as_completion():
        return
    if _opted_out():
        return
    if not _is_interactive_terminal():
        return

    import shellingham

    try:
        shell, _shell_path = shellingham.detect_shell()
    except Exception:
        return

    shell = (shell or "").lower()
    if shell not in _SUPPORTED_SHELLS:
        return

    marker = _marker_path(shell)
    if marker.exists():
        return

    from typer._completion_shared import install

    prog_name = "v2hub"
    installed_shell, installed_path = install(shell=shell, prog_name=prog_name)

    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(str(installed_path))

    # One-line, one-time notice -- printed to stderr so it never pollutes
    # piped/redirected stdout, and doesn't get parsed as command output.
    print(
        f"[v2hub] Enabled {installed_shell} tab-completion (restart your "
        f"shell, or run: source {installed_path})",
        file=sys.stderr,
    )
