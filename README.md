# Context Usage Reminder for Claude Code

A Claude Code hook that monitors context usage and reminds you to save learnings to CLAUDE.md before the context window fills up.

## What it does

- Runs after every tool call (`PostToolUse` hook) - catches context growth during extended work
- Checks current context usage from the transcript
- When usage exceeds threshold (default 95%), shows a non-blocking reminder at every 1% increase
- Your message goes through normally - no interruption

## Installation

### Via Plugin (Recommended)

```bash
# Add the marketplace
/plugin marketplace add YOUR_USERNAME/context-usage-reminder

# Install the plugin
/plugin install context-usage-reminder
```

Then add the environment variables to your `~/.claude/settings.json`:

```json
{
  "env": {
    "CONTEXT_REMINDER_MAX_TOKENS": "200000",
    "CONTEXT_REMINDER_THRESHOLD": "0.95"
  }
}
```

### Manual Installation

1. Copy the hook script to your Claude hooks directory:

```bash
mkdir -p ~/.claude/hooks
cp hooks/context-reminder.py ~/.claude/hooks/
chmod +x ~/.claude/hooks/context-reminder.py
```

2. Add the hook configuration to your `~/.claude/settings.json`:

```json
{
  "env": {
    "CONTEXT_REMINDER_MAX_TOKENS": "200000",
    "CONTEXT_REMINDER_THRESHOLD": "0.95"
  },
  "hooks": {
    "PostToolUse": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/context-reminder.py",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

## Configuration

Environment variables (set in `settings.json` under `env`):

| Variable | Default | Description |
|----------|---------|-------------|
| `CONTEXT_REMINDER_MAX_TOKENS` | `200000` | Maximum context window size |
| `CONTEXT_REMINDER_THRESHOLD` | `0.95` | Percentage at which to warn (0.95 = 95%) |

## How it works

1. Parses the Claude Code transcript JSONL to get actual token usage
2. Calculates total context: `input_tokens + cache_read_input_tokens + cache_creation_input_tokens`
3. When usage exceeds threshold, shows a non-blocking warning via `systemMessage`
4. Warns again at **every 1% increase** above threshold (so you won't miss it)
5. Resets when context drops below threshold (after compaction)

## Performance

The hook parses the transcript file on every message. Performance scales linearly with file size:

| Transcript Size | Parse Time |
|-----------------|------------|
| 1 MB | ~2 ms |
| 3-5 MB | ~8-10 ms |
| 37 MB | ~140 ms |

**Typical 200k token session:** 4-8 MB → 10-20 ms (negligible latency)

Worst case with massive code dumps could reach 60 MB (~200 ms), but this is rare.

## Requirements

- Python 3.6+
- Claude Code with hooks support
- (Optional) `claude-md-management` plugin for the `/claude-md-management:revise-claude-md` command

## State Files

The hook tracks warning state in `~/.cache/claude-hooks/`:

```
~/.cache/claude-hooks/
└── warned-{session_hash}    # Contains: last warned percentage (e.g., "96")
```

- **Filename**: `warned-` + MD5 hash of transcript path (12 chars)
- **Contents**: The percentage at which the last warning was shown
- **Lifecycle**: Deleted when context drops below threshold (after compaction)

Files are auto-deleted when context drops below threshold (compaction). Orphaned files from sessions closed without compaction are tiny (~5 bytes) and safe to ignore or manually clean with `rm ~/.cache/claude-hooks/warned-*`.

## Development

### Manual Testing

To test the hook, temporarily set a low threshold:

```json
"CONTEXT_REMINDER_THRESHOLD": "0.01"
```

Then send any message - the hook will trigger immediately. Remember to set it back to `0.95` after testing.

### Running Unit Tests

```bash
# With pytest (recommended - prettier output)
pip install pytest
pytest tests/ -v

# Or with unittest
python -m unittest tests/test_context_reminder.py -v
```

## License

MIT
