"""Shared pytest configuration."""

import os

# Keep the test suite from appending to the rotating production log file.
# Tests that exercise file logging set LOG_TO_FILE explicitly.
os.environ.setdefault("LOG_TO_FILE", "false")
