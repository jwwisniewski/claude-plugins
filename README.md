# Claude Plugins

[![Tests](https://github.com/jwwisniewski/claude-plugins/actions/workflows/test.yml/badge.svg)](https://github.com/jwwisniewski/claude-plugins/actions/workflows/test.yml)

A collection of Claude Code plugins by Jakub Wisniewski.

## Installation

```bash
# Add the marketplace
/plugin marketplace add jwwisniewski/claude-plugins

# Install a plugin
/plugin install context-usage-reminder
```

Works out of the box with defaults (95% threshold, 200k max tokens).

**Optional** - customize in `~/.claude/settings.json`:

```json
{
  "env": {
    "CONTEXT_REMINDER_MAX_TOKENS": "200000",
    "CONTEXT_REMINDER_THRESHOLD": "0.90"
  }
}
```

## Available Plugins

### [context-usage-reminder](./plugins/context-usage-reminder)

Monitors context usage and reminds you to save learnings before the context window fills up.

- Runs after every tool call (`PostToolUse` hook)
- Shows non-blocking reminder at every 1% increase above threshold (default 95%)
- Resets after context compaction

## Security

See [SECURITY.md](./SECURITY.md) for the security review report.

## License

MIT
