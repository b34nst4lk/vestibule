"""
.env file reading for Vestibule.

The server loads a user-managed .env file into the process environment at
startup (see :func:`load_env_into_environment`); it never writes one. The
file is owned by the user/operator.
"""

import os
from pathlib import Path


def load_env_file(path: str | Path) -> dict[str, str]:
    """
    Load a .env file into a dict, handling double-quoted values.

    Supports common dotenv conveniences: an optional ``export`` prefix,
    double-quoted values, and inline comments on unquoted values.

    Args:
        path: Path to the .env file to read.

    Returns:
        dict[str, str]: Mapping of variable name to value.
    """
    result: dict[str, str] = {}
    if not Path(path).exists():
        return result

    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export ") :]
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1].replace('\\"', '"').replace("\\\\", "\\")
        else:
            # Drop inline comments on unquoted values.
            value = value.split(" #", 1)[0].strip()
        result[key] = value
    return result


def load_env_into_environment(path: str | Path = ".env") -> None:
    """
    Load a .env file into ``os.environ`` without overriding existing values.

    Mirrors python-dotenv's ``override=False`` default: environment
    variables already set take precedence over file values. No-op if the
    file is absent.

    Args:
        path: Path to the .env file to load.
    """
    for key, value in load_env_file(path).items():
        os.environ.setdefault(key, value)
