#!/usr/bin/env python3
"""
PostToolUse hook that reminds user to run /claude-md-management:revise-claude-md
when context usage is high (>95% by default).

This hook runs after every tool call, reads token usage from the transcript,
and warns at every 1% increase above threshold.
"""

import json
import os
import sys
import hashlib

# Configuration (read from environment variables, with defaults)
MAX_CONTEXT_TOKENS = int(os.environ.get("CONTEXT_REMINDER_MAX_TOKENS", "200000"))
THRESHOLD_PERCENT = float(os.environ.get("CONTEXT_REMINDER_THRESHOLD", "0.95"))
STATE_DIR = os.path.expanduser("~/.cache/claude-hooks")


def get_token_usage_from_transcript(transcript_path: str) -> dict:
    """
    Parse transcript JSONL and extract the latest token usage.

    Returns dict with:
        - input_tokens: Direct input tokens
        - cache_read_input_tokens: Tokens read from cache (context from previous turns)
        - output_tokens: Output tokens
        - total_context: Estimated total context usage
    """
    usage = {
        "input_tokens": 0,
        "cache_read_input_tokens": 0,
        "cache_creation_input_tokens": 0,
        "output_tokens": 0,
        "total_context": 0
    }

    try:
        with open(transcript_path, 'r') as f:
            # Read all lines and find the last one with usage data
            last_usage = None
            for line in f:
                if '"usage"' in line:
                    try:
                        # Parse the entire line as JSON and extract usage
                        data = json.loads(line)
                        # Check top-level usage
                        if isinstance(data.get('usage'), dict):
                            last_usage = data['usage']
                        # Check usage nested in message
                        elif isinstance(data.get('message'), dict):
                            msg = data['message']
                            if isinstance(msg.get('usage'), dict):
                                last_usage = msg['usage']
                    except json.JSONDecodeError:
                        pass

            if last_usage:
                usage["input_tokens"] = last_usage.get("input_tokens", 0)
                usage["cache_read_input_tokens"] = last_usage.get("cache_read_input_tokens", 0)
                usage["cache_creation_input_tokens"] = last_usage.get("cache_creation_input_tokens", 0)
                usage["output_tokens"] = last_usage.get("output_tokens", 0)

                # Total context = what's being sent to the model
                # This is approximately: input + cached content
                usage["total_context"] = (
                    usage["input_tokens"] +
                    usage["cache_read_input_tokens"] +
                    usage["cache_creation_input_tokens"]
                )

    except (OSError, IOError) as e:
        print(f"Error reading transcript: {e}", file=sys.stderr)

    return usage


def get_session_id(transcript_path: str) -> str:
    """Generate a unique session ID from transcript path."""
    return hashlib.md5(transcript_path.encode()).hexdigest()[:12]


def get_last_warned_percent(session_id: str) -> int:
    """Get the percentage at which we last warned, or 0 if never warned."""
    state_file = os.path.join(STATE_DIR, f"warned-{session_id}")
    try:
        with open(state_file, 'r') as f:
            return int(f.read().strip() or 0)
    except (OSError, ValueError):
        return 0


def should_warn(session_id: str, current_percent: int, threshold_percent: int) -> bool:
    """
    Check if we should warn about high context.

    Returns True if:
    - We're above threshold AND haven't warned at this percentage level yet
    - Warns at every 1% increase above threshold
    """
    if current_percent < threshold_percent:
        return False

    last_warned = get_last_warned_percent(session_id)
    # Warn if we've never warned, or if we've increased by at least 1%
    return current_percent > last_warned


def mark_warned(session_id: str, current_percent: int) -> None:
    """Mark that we've warned at this percentage level."""
    os.makedirs(STATE_DIR, exist_ok=True)
    state_file = os.path.join(STATE_DIR, f"warned-{session_id}")
    with open(state_file, 'w') as f:
        f.write(str(current_percent))


def clear_warned_if_below_threshold(session_id: str, current_percent: int, threshold_percent: int) -> None:
    """Clear warned state if context dropped below threshold (compaction or new session)."""
    if current_percent < threshold_percent:
        state_file = os.path.join(STATE_DIR, f"warned-{session_id}")
        try:
            os.remove(state_file)
        except OSError:
            pass


def main():
    try:
        # Read hook input from stdin
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        # On error, allow prompt
        sys.exit(0)

    # Get transcript path
    transcript_path = input_data.get("transcript_path", "")
    if not transcript_path or not os.path.exists(transcript_path):
        sys.exit(0)

    session_id = get_session_id(transcript_path)

    # Get actual token usage from transcript
    usage = get_token_usage_from_transcript(transcript_path)
    total_tokens = usage["total_context"]
    usage_percent = int((total_tokens / MAX_CONTEXT_TOKENS) * 100)
    threshold_percent = int(THRESHOLD_PERCENT * 100)

    # Clear warned state if context dropped below threshold (compaction)
    clear_warned_if_below_threshold(session_id, usage_percent, threshold_percent)

    # Warn at every 1% increase above threshold
    if should_warn(session_id, usage_percent, threshold_percent):
        mark_warned(session_id, usage_percent)
        output = {
            "continue": True,
            "systemMessage": f"⚠️ Context {usage_percent}% full - consider /claude-md-management:revise-claude-md"
        }
        print(json.dumps(output))
    # else: Context is fine, allow prompt silently

    sys.exit(0)


if __name__ == "__main__":
    main()
