"""Offline entry point for issue 133; no provider or database credentials required."""

import os
import socket
import sys
from pathlib import Path

import pytest


def deny_network(*args, **kwargs):
    raise RuntimeError("Issue 133: network connections are forbidden")


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    sys.path.insert(0, str(root))
    for key in ("OPENROUTER_API_KEY", "OPENAI_API_KEY", "SENTRY_DSN"):
        os.environ[key] = ""
        os.environ[f"{key}_FILE"] = ""
    os.environ["USE_SQLITE_FOR_TESTS"] = "1"
    os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.test"
    socket.socket.connect = deny_network
    socket.socket.connect_ex = deny_network
    socket.create_connection = deny_network
    args = sys.argv[1:] or ["tests/test_issue133_rsd_validation.py"]
    raise SystemExit(pytest.main(["-q", "--no-cov", "-p", "no:cacheprovider", *args]))
