#!/usr/bin/env python
"""Entry point for running the UI server."""

from vibe.ui_server import run_ui_server

if __name__ == "__main__":
    run_ui_server("127.0.0.1", 5123)
