#!/usr/bin/env python3
"""Tests for context-reminder hook."""

import json
import os
import sys
import tempfile
import shutil
import unittest
from unittest.mock import patch
from io import StringIO

# Add hooks directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'hooks'))

# Import the module (without .py extension)
import importlib.util
spec = importlib.util.spec_from_file_location(
    "context_reminder",
    os.path.join(os.path.dirname(__file__), '..', 'hooks', 'context-reminder.py')
)
context_reminder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(context_reminder)


class TestGetTokenUsageFromTranscript(unittest.TestCase):
    """Tests for parsing token usage from transcript."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_parses_usage_from_transcript(self):
        """Should extract token usage from transcript JSONL."""
        transcript = os.path.join(self.temp_dir, 'transcript.jsonl')
        with open(transcript, 'w') as f:
            # Test nested format (message.usage) as used by Claude Code
            f.write('{"message": {"usage": {"input_tokens": 1000, "cache_read_input_tokens": 5000, "cache_creation_input_tokens": 500, "output_tokens": 200}}}\n')

        usage = context_reminder.get_token_usage_from_transcript(transcript)

        self.assertEqual(usage['input_tokens'], 1000)
        self.assertEqual(usage['cache_read_input_tokens'], 5000)
        self.assertEqual(usage['cache_creation_input_tokens'], 500)
        self.assertEqual(usage['output_tokens'], 200)
        self.assertEqual(usage['total_context'], 6500)  # 1000 + 5000 + 500

    def test_returns_last_usage_entry(self):
        """Should return the most recent usage data."""
        transcript = os.path.join(self.temp_dir, 'transcript.jsonl')
        with open(transcript, 'w') as f:
            f.write('{"message": {"usage": {"input_tokens": 100, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0, "output_tokens": 50}}}\n')
            f.write('{"message": {"usage": {"input_tokens": 2000, "cache_read_input_tokens": 10000, "cache_creation_input_tokens": 1000, "output_tokens": 500}}}\n')

        usage = context_reminder.get_token_usage_from_transcript(transcript)

        self.assertEqual(usage['input_tokens'], 2000)
        self.assertEqual(usage['total_context'], 13000)

    def test_handles_missing_file(self):
        """Should return zeros for missing file."""
        usage = context_reminder.get_token_usage_from_transcript('/nonexistent/path')

        self.assertEqual(usage['total_context'], 0)

    def test_handles_empty_file(self):
        """Should return zeros for empty file."""
        transcript = os.path.join(self.temp_dir, 'empty.jsonl')
        with open(transcript, 'w') as f:
            pass

        usage = context_reminder.get_token_usage_from_transcript(transcript)

        self.assertEqual(usage['total_context'], 0)


class TestSessionState(unittest.TestCase):
    """Tests for session warning state tracking."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.original_state_dir = context_reminder.STATE_DIR
        context_reminder.STATE_DIR = self.temp_dir

    def tearDown(self):
        context_reminder.STATE_DIR = self.original_state_dir
        shutil.rmtree(self.temp_dir)

    def test_session_id_is_deterministic(self):
        """Same transcript path should produce same session ID."""
        id1 = context_reminder.get_session_id('/path/to/transcript.jsonl')
        id2 = context_reminder.get_session_id('/path/to/transcript.jsonl')
        self.assertEqual(id1, id2)

    def test_different_paths_produce_different_ids(self):
        """Different transcript paths should produce different session IDs."""
        id1 = context_reminder.get_session_id('/path/one/transcript.jsonl')
        id2 = context_reminder.get_session_id('/path/two/transcript.jsonl')
        self.assertNotEqual(id1, id2)

    def test_should_warn_returns_true_when_above_threshold(self):
        """Should return True if above threshold and not warned yet."""
        session_id = 'test-session-123'
        self.assertTrue(context_reminder.should_warn(session_id, 96, 95))

    def test_should_warn_returns_false_below_threshold(self):
        """Should return False if below threshold."""
        session_id = 'test-session-123'
        self.assertFalse(context_reminder.should_warn(session_id, 90, 95))

    def test_should_warn_returns_false_at_same_percent(self):
        """Should return False after warning at same percentage."""
        session_id = 'test-session-456'
        context_reminder.mark_warned(session_id, 96)
        self.assertFalse(context_reminder.should_warn(session_id, 96, 95))

    def test_should_warn_returns_true_at_higher_percent(self):
        """Should return True when percentage increases by 1%."""
        session_id = 'test-session-789'
        context_reminder.mark_warned(session_id, 96)
        self.assertTrue(context_reminder.should_warn(session_id, 97, 95))

    def test_clear_warned_below_threshold(self):
        """Should clear state when context drops below threshold."""
        session_id = 'test-session-abc'
        context_reminder.mark_warned(session_id, 96)
        context_reminder.clear_warned_if_below_threshold(session_id, 50, 95)
        # Now should warn again at 96%
        self.assertTrue(context_reminder.should_warn(session_id, 96, 95))


class TestMainFunction(unittest.TestCase):
    """Integration tests for main hook function."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.original_state_dir = context_reminder.STATE_DIR
        context_reminder.STATE_DIR = self.temp_dir

    def tearDown(self):
        context_reminder.STATE_DIR = self.original_state_dir
        shutil.rmtree(self.temp_dir)

    def create_transcript(self, input_tokens, cache_read, cache_creation):
        """Helper to create a transcript file with usage data."""
        transcript = os.path.join(self.temp_dir, 'transcript.jsonl')
        usage = {
            "input_tokens": input_tokens,
            "cache_read_input_tokens": cache_read,
            "cache_creation_input_tokens": cache_creation,
            "output_tokens": 100
        }
        with open(transcript, 'w') as f:
            f.write(json.dumps({"usage": usage}) + '\n')
        return transcript

    @patch.object(context_reminder, 'MAX_CONTEXT_TOKENS', 100000)
    @patch.object(context_reminder, 'THRESHOLD_PERCENT', 0.95)
    def test_no_output_when_below_threshold(self):
        """Should produce no output when context is below threshold."""
        transcript = self.create_transcript(1000, 5000, 500)  # 6500 tokens = 6.5%
        input_data = json.dumps({"transcript_path": transcript})

        with patch('sys.stdin', StringIO(input_data)):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                with self.assertRaises(SystemExit) as cm:
                    context_reminder.main()

        self.assertEqual(cm.exception.code, 0)
        self.assertEqual(mock_stdout.getvalue(), '')

    @patch.object(context_reminder, 'MAX_CONTEXT_TOKENS', 100000)
    @patch.object(context_reminder, 'THRESHOLD_PERCENT', 0.05)  # 5% threshold for testing
    def test_outputs_reminder_when_above_threshold(self):
        """Should output reminder when context exceeds threshold."""
        transcript = self.create_transcript(5000, 5000, 500)  # 10500 tokens = 10.5%
        input_data = json.dumps({"transcript_path": transcript})

        with patch('sys.stdin', StringIO(input_data)):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                with self.assertRaises(SystemExit) as cm:
                    context_reminder.main()

        self.assertEqual(cm.exception.code, 0)
        output = mock_stdout.getvalue()
        # Check JSON output with systemMessage
        output_json = json.loads(output)
        self.assertTrue(output_json.get('continue'))
        self.assertIn('Context', output_json.get('systemMessage', ''))
        self.assertIn('/claude-md-management:revise-claude-md', output_json.get('systemMessage', ''))

    @patch.object(context_reminder, 'MAX_CONTEXT_TOKENS', 100000)
    @patch.object(context_reminder, 'THRESHOLD_PERCENT', 0.05)
    def test_warns_at_each_percent_increase(self):
        """Should warn at each 1% increase above threshold."""
        transcript = os.path.join(self.temp_dir, 'transcript.jsonl')

        def update_transcript(input_tokens, cache_read, cache_creation):
            usage = {
                "input_tokens": input_tokens,
                "cache_read_input_tokens": cache_read,
                "cache_creation_input_tokens": cache_creation,
                "output_tokens": 100
            }
            with open(transcript, 'w') as f:
                f.write(json.dumps({"message": {"usage": usage}}) + '\n')

        input_data = json.dumps({"transcript_path": transcript})

        # First call at 10% - should warn (above 5% threshold)
        update_transcript(5000, 5000, 0)  # 10000 tokens = 10%
        with patch('sys.stdin', StringIO(input_data)):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                with self.assertRaises(SystemExit):
                    context_reminder.main()
        self.assertIn('systemMessage', mock_stdout.getvalue())

        # Second call at same 10% - should NOT warn
        with patch('sys.stdin', StringIO(input_data)):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                with self.assertRaises(SystemExit):
                    context_reminder.main()
        self.assertEqual(mock_stdout.getvalue(), '')

        # Third call at 11% - should warn again
        update_transcript(5500, 5500, 0)  # 11000 tokens = 11%
        with patch('sys.stdin', StringIO(input_data)):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                with self.assertRaises(SystemExit):
                    context_reminder.main()
        self.assertIn('systemMessage', mock_stdout.getvalue())

    @patch.object(context_reminder, 'MAX_CONTEXT_TOKENS', 100000)
    @patch.object(context_reminder, 'THRESHOLD_PERCENT', 0.10)  # 10% threshold
    def test_warns_again_after_compaction(self):
        """Should warn again after context drops below threshold (compaction)."""
        transcript = os.path.join(self.temp_dir, 'transcript.jsonl')

        def update_transcript(input_tokens, cache_read, cache_creation):
            usage = {
                "input_tokens": input_tokens,
                "cache_read_input_tokens": cache_read,
                "cache_creation_input_tokens": cache_creation,
                "output_tokens": 100
            }
            with open(transcript, 'w') as f:
                f.write(json.dumps({"message": {"usage": usage}}) + '\n')

        input_data = json.dumps({"transcript_path": transcript})

        # First call at 15% - should warn (above 10% threshold)
        update_transcript(7500, 7500, 0)  # 15000 tokens = 15%
        with patch('sys.stdin', StringIO(input_data)):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                with self.assertRaises(SystemExit):
                    context_reminder.main()
        self.assertIn('systemMessage', mock_stdout.getvalue())

        # Simulate compaction - drops below threshold to 5%
        update_transcript(2500, 2500, 0)  # 5000 tokens = 5%
        with patch('sys.stdin', StringIO(input_data)):
            with self.assertRaises(SystemExit):
                context_reminder.main()

        # Back to 15% - should warn again since state was cleared
        update_transcript(7500, 7500, 0)  # 15000 tokens = 15%
        with patch('sys.stdin', StringIO(input_data)):
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                with self.assertRaises(SystemExit):
                    context_reminder.main()
        self.assertIn('systemMessage', mock_stdout.getvalue())


if __name__ == '__main__':
    unittest.main()
