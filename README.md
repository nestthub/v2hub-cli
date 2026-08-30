# V2Hub CLI - Command-Line Interface for VPN Subscription API

Beautiful, user-friendly command-line interface for V2Hub VPN Subscription API with optional admin commands.

### 🌐 Part of the [V2Hub Ecosystem](https://github.com/nestthub/nestthub/blob/main/ecosystems/v2hub/README.md)

This package is one component of V2Hub — see the full project overview, architecture, and all related repositories.

## Features

- 🎨 **Beautiful Output**: Rich formatting with colors and tables
- ⚡ **Fast & Intuitive**: Simple commands for all operations
- 🔧 **Regular Commands**: Full access to subscription management
- 🤝 **Provider Commands**: Manage subscriptions on behalf of end-users (`v2hub provider <user_id> ...`)
- 🔐 **Admin Commands**: Optional admin operations (requires v2hub-admin) — users, providers, IP bans, whitelist
- 🎯 **Type Safe**: Full type hints, powered by Typer

## Installation

### Basic Installation

```bash
# Install CLI (includes v2hub automatically)
pip install v2hub-cli
```

### With Admin Support

```bash
# Install CLI with admin commands
pip install v2hub-cli[admin]
```

## Usage

After installation, the `v2hub` command is available:

```bash
v2hub --help
```

### Shell Autocompletion

`v2hub` supports tab-completion of commands, subcommands, options, and —
where it can — real values pulled live from the API: subscription
tokens, config hashes, provider hashes, and banned/whitelisted IPs. This
works the same way `git` does — type a partial command, press `Tab`,
and either complete it or cycle through matching suggestions.

Completion is set up automatically the first time you run `v2hub` in an
interactive shell (bash, zsh, or fish) — nothing to install or type.
Just restart your shell (or open a new terminal) after the first run,
then try:

```bash
v2hub get<TAB>                 # -> suggests real subscription tokens
v2hub update-config <token> --config-id <TAB>   # -> suggests config hashes for that subscription
v2hub provider <TAB>
```

In shells that support it (zsh, fish — not bash, which has no
equivalent display), each suggestion is shown together with a short
hint so you can tell entries apart, e.g. a subscription token next to
its name, or a config hash next to its comment/URL:

```
abc123de…  My Personal VPN
f91a02bb…  My Work VPN
```

Only the value itself (the token or hash) is ever inserted — the hint
is just there to help you pick the right one.

If you'd rather manage this yourself, opt out of the automatic setup
with `export V2HUB_NO_AUTOCOMPLETE=1`, then install (or print) the
completion script manually:

```bash
v2hub --install-completion         # install for your current shell
v2hub --show-completion            # print the script for your shell
v2hub --show-completion bash       # or force a specific shell
```

### Basic Commands

```bash
# Show version
v2hub version

# List all subscriptions
v2hub list

# Create a subscription
v2hub create "my-vpn"

# Get subscription details
v2hub get <token>

# Add sources to subscription
v2hub add-sources <token> -s vless://server1 -s vmess://server2

# Refresh external URL sources
v2hub refresh <token>

# Delete subscription
v2hub delete <token>

# Show your own account info
v2hub me

# Fetch a subscription's public configs
v2hub public <token> [--decode]
```

### Connection Commands

Manage the current user's own connections to providers:

```bash
v2hub connection list
v2hub connection get <provider_name>
v2hub connection approve <provider_name>
v2hub connection reject <provider_name> [--force]
v2hub connection revoke <provider_name> [--force]
```

### Admin Commands

Admin commands are available only if `v2hub-admin` is installed. They use `--secret-key`/`V2HUB_ADMIN_SECRET` (HMAC auth) instead of `--api-token`:

```bash
# Show admin help
v2hub admin --help

# Show admin module version
v2hub admin version

# User management
v2hub admin create-user <user_id>
v2hub admin get-user <user_id>
v2hub admin delete-user <user_id>
v2hub admin set-user-status <user_id> --active|--inactive
v2hub admin refresh-token <user_id>

# Provider management
v2hub admin create-provider <owner_hash> <provider_name> [--provider-url <url>]
v2hub admin get-providers
v2hub admin get-provider <provider_hash>
v2hub admin get-provider-by-name <provider_name>
v2hub admin get-provider-by-owner-id <owner_id>
v2hub admin delete-provider <provider_hash>
v2hub admin set-provider-status <provider_hash> --active|--inactive
v2hub admin update-provider-url <provider_hash> --provider-url <url>
v2hub admin update-provider-name <provider_hash> --provider-name <name>
v2hub admin refresh-provider-token <provider_hash>

# User <-> provider connections
v2hub admin get-user-providers <user_id>
v2hub admin get-user-provider <user_id> <provider_name>

# Provider authorization workflow
v2hub admin get-provider-authorization <provider_name> <user_id>
v2hub admin process-provider-authorization <user_id> <provider_name> [--hmac <hmac>]
v2hub admin approve-provider-authorization <user_id> <provider_name>
v2hub admin reject-provider-authorization <user_id> <provider_name> [--force]

# IP ban management
v2hub admin ban-ip <ip_address> [--duration <seconds>]
v2hub admin unban-ip <ip_address>
v2hub admin ban-status <ip_address>
v2hub admin ban-list

# Whitelist management
v2hub admin whitelist-add <ip_or_cidr> [--description <text>]
v2hub admin whitelist-remove <ip_or_cidr>
v2hub admin whitelist-list
```

### Provider Commands

If your API token belongs to a **provider** account, `v2hub provider <user_id> ...` manages subscriptions on behalf of a specific end-user. Every top-level subscription command has a provider-scoped counterpart, plus connection lifecycle commands:

```bash
# Connection lifecycle
v2hub provider <user_id> connection-get
v2hub provider <user_id> connection-create
v2hub provider <user_id> connection-revoke [--force]
v2hub provider <user_id> connection-delete [--force]

# Subscriptions, scoped to that user
v2hub provider <user_id> list
v2hub provider <user_id> create "vpn-name" -s vless://server1
v2hub provider <user_id> get <token>
v2hub provider <user_id> add-sources <token> -s vless://server1
v2hub provider <user_id> replace-sources <token> -s vless://server1
v2hub provider <user_id> remove-sources <token> -s <source-id> [--force]
v2hub provider <user_id> delete <token> [--force]
v2hub provider <user_id> update <token> --name "new-name"
v2hub provider <user_id> update-config <token> --config-id <id> [--hidden/--visible] [--max-depth 0-3]
v2hub provider <user_id> refresh <token>
```

An approved connection (`connection-create`) must exist before any of the subscription commands above will succeed for that `user_id`.

### Environment Variables

Configure the CLI using environment variables (there is no config file — every command also accepts `--base-url`/`-u` and `--api-token`/`-t` directly, which take precedence over the env vars):

```bash
# Required
export V2HUB_API_URL="https://api.example.com"
export V2HUB_API_TOKEN="your-api-token"

# For admin commands (optional, uses --secret-key / -k instead of --api-token)
export V2HUB_ADMIN_SECRET="your-hmac-secret"

# Then use commands
v2hub list
v2hub admin get-user 12345  # if v2hub-admin is installed
```

## Examples

### Create and Configure Subscription

```bash
# Create subscription
v2hub create "work-vpn" --description "Office VPN servers"

# Add sources
v2hub add-sources <token> \
  -s vless://server1.example.com:443 \
  -s vmess://server2.example.com:443

# View subscription details, including its sources
v2hub get <token>
```

### List and Filter

```bash
# List all your subscriptions
v2hub list

# Get specific subscription
v2hub get <token>
```

### Update Subscription

```bash
# Update name
v2hub update <token> --name "new-name"

# Update description
v2hub update <token> --description "Updated description"

# Update a specific config's comment/visibility/nesting depth
v2hub update-config <token> --config-id <id> --comment "Server 1" --hidden --max-depth 1

# Replace all sources
v2hub replace-sources <token> -s vless://new-server
```

### Admin Operations

```bash
# Create a user (requires admin)
v2hub admin create-user 12345

# Get user info (requires admin)
v2hub admin get-user 12345

# Ban an IP for 1 hour (requires admin)
v2hub admin ban-ip 192.168.1.100 --duration 3600

# List whitelist entries (requires admin)
v2hub admin whitelist-list
```

## Output

Subscription listings are rendered as a Rich-formatted table; single-resource commands (`get`, `create`, `update`, etc.) print a key/value panel. There is currently no `--format` flag — for scripting, parse the plain text output or use the Python `v2hub` client directly.

## Command Reference

### Regular Commands

| Command                                     | Description                                |
| ------------------------------------------- | ------------------------------------------ |
| `v2hub version`                             | Show version information                   |
| `v2hub list`                                | List your subscriptions                    |
| `v2hub create <name>`                       | Create new subscription                    |
| `v2hub get <token>`                         | Get subscription details                   |
| `v2hub update <token>`                      | Update subscription name/description       |
| `v2hub update-config <token>`               | Update a config's comment/visibility/depth |
| `v2hub delete <token>`                      | Delete subscription                        |
| `v2hub add-sources <token> -s <uri>...`     | Add sources                                |
| `v2hub remove-sources <token> -s <id>...`   | Remove sources                             |
| `v2hub replace-sources <token> -s <uri>...` | Replace all sources                        |
| `v2hub refresh <token>`                     | Refresh external URL sources               |
| `v2hub me`                                  | Show your own account info                 |
| `v2hub public <token>`                      | Fetch a subscription's public configs      |

### Connection Commands

| Command                                       | Description                              |
| ---------------------------------------------- | ---------------------------------------- |
| `v2hub connection list`                       | List your connections to providers       |
| `v2hub connection get <provider_name>`        | Get your connection status for a provider|
| `v2hub connection approve <provider_name>`    | Approve a pending connection request     |
| `v2hub connection reject <provider_name>`     | Reject a pending connection request      |
| `v2hub connection revoke <provider_name>`     | Revoke your authorization for a provider |

### Provider Commands

| Command                                            | Description                             |
| -------------------------------------------------- | --------------------------------------- |
| `v2hub provider <user_id> connection-get`          | Get authorization status for a user     |
| `v2hub provider <user_id> connection-create`       | Create/re-approve authorization         |
| `v2hub provider <user_id> connection-revoke`       | Revoke authorization                    |
| `v2hub provider <user_id> connection-delete`       | Permanently delete authorization record |
| `v2hub provider <user_id> list`                    | List that user's subscriptions          |
| `v2hub provider <user_id> create <name>`           | Create subscription for that user       |
| `v2hub provider <user_id> get <token>`             | Get their subscription details          |
| `v2hub provider <user_id> update <token>`          | Update their subscription               |
| `v2hub provider <user_id> update-config <token>`   | Update a config on their subscription   |
| `v2hub provider <user_id> delete <token>`          | Delete their subscription               |
| `v2hub provider <user_id> add-sources <token>`     | Add sources                             |
| `v2hub provider <user_id> replace-sources <token>` | Replace sources                         |
| `v2hub provider <user_id> remove-sources <token>`  | Remove sources                          |
| `v2hub provider <user_id> refresh <token>`         | Refresh external URL sources            |

### Admin Commands (Optional)

| Command                                              | Description                   |
| ---------------------------------------------------- | ----------------------------- |
| `v2hub admin --help`                                 | Show admin commands help      |
| `v2hub admin version`                                | Show admin module version     |
| `v2hub admin create-user <user_id>`                  | Create user                   |
| `v2hub admin get-user <user_id>`                     | Get user info                 |
| `v2hub admin delete-user <user_id>`                  | Delete user                   |
| `v2hub admin set-user-status <user_id>`              | Activate/deactivate user      |
| `v2hub admin refresh-token <user_id>`                | Refresh user's API token      |
| `v2hub admin create-provider <owner_hash> <name>`    | Create provider account       |
| `v2hub admin get-providers`                          | List all providers            |
| `v2hub admin get-provider <provider_hash>`           | Get provider info             |
| `v2hub admin delete-provider <provider_hash>`        | Delete provider               |
| `v2hub admin set-provider-status <provider_hash>`    | Activate/deactivate provider  |
| `v2hub admin update-provider-url <provider_hash>`    | Update provider URL           |
| `v2hub admin update-provider-name <provider_hash>`   | Update provider name          |
| `v2hub admin refresh-provider-token <provider_hash>` | Refresh provider's API token  |
| `v2hub admin get-provider-by-name <name>`            | Look up provider by name      |
| `v2hub admin get-provider-by-owner-id <owner_id>`    | Look up provider by owner ID  |
| `v2hub admin get-user-providers <user_id>`           | List a user's provider connections |
| `v2hub admin get-user-provider <user_id> <name>`     | Get one user/provider connection |
| `v2hub admin get-provider-authorization <name> <user_id>` | Get authorization state |
| `v2hub admin process-provider-authorization <user_id> <name>` | Process a connection invite |
| `v2hub admin approve-provider-authorization <user_id> <name>` | Approve a pending authorization |
| `v2hub admin reject-provider-authorization <user_id> <name>`  | Reject/revoke an authorization |
| `v2hub admin ban-ip <ip_address>`                    | Ban an IP address             |
| `v2hub admin unban-ip <ip_address>`                  | Unban an IP address           |
| `v2hub admin ban-status <ip_address>`                | Check an IP's ban status      |
| `v2hub admin ban-list`                               | List banned IPs               |
| `v2hub admin whitelist-add <ip_or_cidr>`             | Add IP/CIDR to whitelist      |
| `v2hub admin whitelist-remove <ip_or_cidr>`          | Remove IP/CIDR from whitelist |
| `v2hub admin whitelist-list`                         | List whitelisted IPs          |

## Exit Codes

- `0` - Success
- `1` - Error (authentication, not found, validation, or any other API/CLI error — the CLI does not currently distinguish error types by exit code)
- `2` - Invalid command or arguments (raised by Typer/Click itself)

## Development

```bash
# Install in development mode
pip install -e ".[dev]"

# Install with admin support
pip install -e ".[admin,dev]"

# Run tests
pytest

# Type checking
mypy src/
```

## Optional Dependencies

The CLI has a modular design:

- **Base**: `v2hub` (required, installed automatically)
- **Admin**: `v2hub-admin` (optional, install with `pip install v2hub-cli[admin]`)

If admin module is not installed, admin commands are automatically hidden and disabled.

## Requirements

- **v2hub** (required, installed automatically) >= 1.1.2, < 2.0.0
- **v2hub-admin** >= 1.1.4, < 2.0.0 (optional, for admin commands)
- Python >= 3.10

## Graceful Admin Fallback

When `v2hub-admin` is not installed, the `admin` command group is hidden from `v2hub --help`, but `v2hub admin version` still works and reports the situation:

```bash
$ v2hub admin version
Error: admin client is not available. Install 'v2hub_admin'.

$ v2hub --help
# Shows only regular and provider commands; the admin section is hidden
```

## License

MIT License - see LICENSE file for details.

## Author

nestt
