# Claude Plugins

[![Tests](https://github.com/jwwisniewski/claude-plugins/actions/workflows/test.yml/badge.svg)](https://github.com/jwwisniewski/claude-plugins/actions/workflows/test.yml)

A collection of Claude Code plugins by Jakub Wisniewski.

## Installation

```bash
# Add the marketplace
/plugin marketplace add jwwisniewski/claude-plugins

# List available plugins
/plugin marketplace list

# Install a plugin
/plugin install context-usage-reminder
```

## Available Plugins

### [context-usage-reminder](./plugins/context-usage-reminder)

Monitors context usage and reminds you to save learnings before the context window fills up.

- Runs after every tool call (`PostToolUse` hook)
- Shows non-blocking reminder at every 1% increase above threshold (default 95%)
- Resets after context compaction

**Configuration:**
```json
{
  "env": {
    "CONTEXT_REMINDER_MAX_TOKENS": "200000",
    "CONTEXT_REMINDER_THRESHOLD": "0.95"
  }
}
```

## Security

See [SECURITY.md](./SECURITY.md) for the security review report.

## License

MIT
