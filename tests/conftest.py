"""
Pytest fixtures for Bulwark integration tests.

Provides fixtures for both stdio and HTTP/SSE transport testing.
"""

import os
import sys
import pytest
import json
import asyncio
import time
import subprocess
from pathlib import Path
from typing import AsyncGenerator, Generator

import httpx


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """Create isolated data directory per test."""
    data = tmp_path / "data"
    data.mkdir()
    return data


@pytest.fixture
def env_config(data_dir: Path) -> dict:
    """Environment variables for bulwark server."""
    # Start with current environment and override what we need
    env = {
        **os.environ,
        "EMAIL_SMTP_HOST": "smtp.example.com",
        "EMAIL_SMTP_PORT": "587",
        "EMAIL_SMTP_PASSWORD": "test_password",
        "EMAIL_SENDER_EMAIL": "sender@example.com",
        "EMAIL_WHITELIST": json.dumps({
            "alice": "alice@example.com",
            "bob": "bob@example.com",
        }),
    }
    return env


@pytest.fixture
def http_server(env_config: dict) -> Generator[str, None, None]:
    """
    Start Bulwark HTTP/SSE server and yield its base URL.

    This fixture starts a real HTTP server for integration testing
    using a subprocess. The server runs on port 8080.
    """
    # Path to main.py
    main_py_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "main.py")

    # Set up environment
    for key, value in env_config.items():
        if key == "EMAIL_WHITELIST":
            os.environ[key] = value
        else:
            os.environ[key] = value

    # Start server as subprocess
    proc = subprocess.Popen(
        [sys.executable, main_py_path, "--transport", "http", "--port", "8080"],
        env=env_config,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )

    # Wait for server to be ready
    base_url = "http://127.0.0.1:8080"
    max_retries = 50
    for i in range(max_retries):
        try:
            with httpx.Client() as client:
                response = client.get(f"{base_url}/health", timeout=2.0)
                if response.status_code == 200:
                    break
        except Exception:
            time.sleep(0.1)
    else:
        proc.terminate()
        proc.wait()
        raise RuntimeError("HTTP server failed to start")

    yield base_url

    # Cleanup
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
