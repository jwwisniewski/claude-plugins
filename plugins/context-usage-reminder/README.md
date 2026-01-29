# Context Usage Reminder

Monitors context usage and reminds you to save learnings to CLAUDE.md before the context window fills up.

## What it does

- Runs after every tool call (`PostToolUse` hook) - catches context growth during extended work
- Checks current context usage from the transcript
- When usage exceeds threshold (default 95%), shows a non-blocking reminder at every 1% increase
- Your message goes through normally - no interruption

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

The hook parses the transcript file on every tool call. Performance scales linearly with file size:

| Transcript Size | Parse Time |
|-----------------|------------|
| 1 MB | ~2 ms |
| 3-5 MB | ~8-10 ms |
| 37 MB | ~140 ms |

**Typical 200k token session:** 4-8 MB → 10-20 ms (negligible latency)

## State Files

The hook tracks warning state in `~/.cache/claude-hooks/`:

```
~/.cache/claude-hooks/
└── warned-{session_hash}    # Contains: last warned percentage (e.g., "96")
```

Files are auto-deleted when context drops below threshold (compaction). Orphaned files are tiny (~5 bytes) and safe to ignore.

## Development

### Running Unit Tests

```bash
cd plugins/context-usage-reminder
pytest tests/ -v
```

## Requirements

- Python 3.6+
- Claude Code with hooks support
- (Optional) `claude-md-management` plugin for the `/claude-md-management:revise-claude-md` command
