# V2Hub CLI - Command-Line Interface for VPN Subscription API

Beautiful, user-friendly command-line interface for V2Hub VPN Subscription API with optional admin commands.

## Features

- 🎨 **Beautiful Output**: Rich formatting with colors and tables
- ⚡ **Fast & Intuitive**: Simple commands for all operations
- 🔧 **Regular Commands**: Full access to subscription management
- 🔐 **Admin Commands**: Optional admin operations (requires v2hub-admin)
- 📋 **Multiple Formats**: JSON, table, or minimal output
- 🎯 **Type Safe**: Auto-completion support

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
v2hub add-sources <token> -s vless://server1 vmess://server2

# Get subscription config URL
v2hub config <token>

# Delete subscription
v2hub delete <token>
```

### Admin Commands

Admin commands are available only if `v2hub-admin` is installed:

```bash
# Show admin help
v2hub admin --help

# Show admin version
v2hub admin version

# List all subscriptions in the system (admin)
v2hub admin list-all

# Get any subscription (bypass ownership)
v2hub admin get <token>

# Delete any subscription (admin privilege)
v2hub admin delete <token>

# Get system statistics
v2hub admin stats
```

### Environment Variables

Configure the CLI using environment variables:

```bash
# Required
export V2HUB_API_URL="https://api.example.com"
export V2HUB_API_TOKEN="your-api-token"

# For admin commands (optional)
export V2HUB_ADMIN_SECRET="your-hmac-secret"

# Then use commands
v2hub list
v2hub admin list-all  # if v2hub-admin is installed
```

### Configuration File

Create `~/.v2hub/config.json`:

```json
{
  "api_url": "https://api.example.com",
  "api_token": "your-api-token",
  "admin_secret": "your-hmac-secret"
}
```

## Examples

### Create and Configure Subscription

```bash
# Create subscription
v2hub create "work-vpn" --comment "Office VPN servers"

# Add sources
v2hub add-sources <token> -s\
  vless://server1.example.com:443 \
  vmess://server2.example.com:443

# View sources
v2hub sources <token>

# Get config URL
v2hub config <token>
```

### List and Filter

```bash
# List all your subscriptions
v2hub list

# List with JSON output
v2hub list --format json

# Get specific subscription
v2hub get <token>
```

### Update Subscription

```bash
# Update name
v2hub update <token> --name "new-name"

# Update comment
v2hub update <token> --comment "Updated description"

# Replace all sources
v2hub replace-sources <token> vless://new-server
```

### Admin Operations

```bash
# List all subscriptions (requires admin)
v2hub admin list-all

# Get any subscription (requires admin)
v2hub admin get <any-token>

# Delete any subscription (requires admin)
v2hub admin delete <any-token>

# System statistics (requires admin)
v2hub admin stats
```

## Output Formats

The CLI supports multiple output formats:

```bash
# Table format (default, rich formatting)
v2hub list

# JSON format (for scripting)
v2hub list --format json

# Minimal format (just values)
v2hub list --format minimal
```

## Command Reference

### Regular Commands

| Command                                  | Description              |
| ---------------------------------------- | ------------------------ |
| `v2hub version`                          | Show version information |
| `v2hub list`                             | List your subscriptions  |
| `v2hub create <name>`                    | Create new subscription  |
| `v2hub get <token>`                      | Get subscription details |
| `v2hub update <token>`                   | Update subscription      |
| `v2hub delete <token>`                   | Delete subscription      |
| `v2hub add-sources <token> <uri...>`     | Add sources              |
| `v2hub remove-sources <token> <uri...>`  | Remove sources           |
| `v2hub replace-sources <token> <uri...>` | Replace all sources      |
| `v2hub sources <token>`                  | List sources             |
| `v2hub config <token>`                   | Get subscription config  |
| `v2hub refresh <token>`                  | Refresh subscription     |

### Admin Commands (Optional)

| Command                      | Description                     |
| ---------------------------- | ------------------------------- |
| `v2hub admin --help`         | Show admin commands help        |
| `v2hub admin version`        | Show admin module version       |
| `v2hub admin list-all`       | List all subscriptions (admin)  |
| `v2hub admin get <token>`    | Get any subscription (admin)    |
| `v2hub admin delete <token>` | Delete any subscription (admin) |
| `v2hub admin stats`          | System statistics (admin)       |

## Exit Codes

- `0` - Success
- `1` - General error
- `2` - Invalid command or arguments
- `3` - Authentication error
- `4` - Not found error
- `5` - API error

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

- **v2hub** >= 1.0.0 (required, installed automatically)
- **v2hub-admin** >= 1.0.0 (optional, for admin commands)
- Python >= 3.9

## Graceful Admin Fallback

When `v2hub-admin` is not installed:

```bash
$ v2hub admin --help
Error: Admin commands require the 'v2hub-admin' package.
Install it with: pip install v2hub-admin

$ v2hub --help
# Shows only regular commands, admin section is hidden
```

## License

MIT License - see LICENSE file for details.

## Author

nestt
