"""
``vestibule config`` command family (get/set/unset/list).

git-config-style management of non-secret Vestibule TOML configuration. Keys
are full dotted paths under ``tool.vestibule.`` (e.g. ``tool.vestibule.host``,
``tool.vestibule.plugins.whitelisted_email.smtp_host``).

``set``/``unset`` edit individual keys in a single writable file (project
``.vestibule/config.toml`` by default, ``--user`` for the user file,
``--file <path>`` for a custom path) via ``tomlkit`` round-trip editing, so
comments and formatting are preserved. The Pydantic schema is the source of
truth: unknown keys are refused, and values are coerced/validated against it.
"""

import functools
import os
import tempfile
from pathlib import Path
from typing import Annotated, Any, get_args, get_origin

import tomlkit
import typer
from pydantic import BaseModel, TypeAdapter

from .approval import ApprovalMode
from .config import ApprovalSettings, Config
from .plugin_manager import PluginManager

PREFIX = "tool.vestibule."

config_app = typer.Typer(
    help="Manage Vestibule configuration (get/set/unset/list).",
    invoke_without_command=False,
)


class ConfigError(Exception):
    """Raised for a user-facing config CLI error (printed, exits 1)."""


def _handle(fn):
    """Catch ConfigError and turn it into a clean stderr message + exit 1."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except ConfigError as e:
            typer.echo(str(e), err=True)
            raise typer.Exit(1) from None

    return wrapper


# --- key / file helpers -----------------------------------------------------


def _parse_key(key: str) -> list[str]:
    """Return the dotted path under ``tool.vestibule.``, or raise."""
    if not key.startswith(PREFIX):
        raise ConfigError(f"Key must start with '{PREFIX}', got '{key}'.")
    parts = key[len(PREFIX) :].strip().split(".")
    if not parts or parts == [""]:
        raise ConfigError("Empty key.")
    return parts


def _write_target(user: bool, file: str | None) -> Path:
    if file:
        return Path(file)
    if user:
        return Path.home() / ".vestibule" / "config.toml"
    return Path.cwd() / ".vestibule" / "config.toml"


def _user_path() -> Path:
    return Path.home() / ".vestibule" / "config.toml"


def _project_path() -> Path:
    return Path.cwd() / ".vestibule" / "config.toml"


def _plugin_schemas() -> dict[str, type]:
    pm = PluginManager()
    pm.load_all()
    return pm.get_plugin_config_schemas()


# --- schema / type resolution -----------------------------------------------


def _dict_value_type(ann: Any) -> Any:
    """Return the value type of a ``dict[K, V]`` annotation, else None."""
    if get_origin(ann) is dict:
        args = get_args(ann)
        return args[1] if args else None
    return None


def _leaf_type(parts: list[str], schemas: dict[str, type]) -> Any:
    """Return the target type for a settable leaf key, or None if unknown."""
    first = parts[0]
    field = Config.model_fields.get(first)
    if field is None:
        return None

    if first == "plugins":
        if len(parts) < 3:
            return None
        plugin, fname = parts[1], parts[2]
        schema = schemas.get(plugin)
        if schema is None:
            raise ConfigError(
                f"Plugin '{plugin}' declares no config schema; refusing to set under it."
            )
        pf = schema.model_fields.get(fname)
        if pf is None:
            return None
        ann = pf.annotation
        for _deeper in parts[3:]:
            ann = _dict_value_type(ann)
            if ann is None:
                return None
        return ann

    if first == "rate_limits":
        return int  # dict[str, int]

    if first == "approval":
        if len(parts) < 2:
            return None
        sub = parts[1]
        if sub == "overrides":
            return ApprovalMode  # dict[str, ApprovalMode]
        af = ApprovalSettings.model_fields.get(sub)
        return af.annotation if af else None

    return field.annotation


def _coerce(typ: Any, raw: str) -> Any:
    """Coerce a CLI string to ``typ``, returning a toml-writable plain value."""
    try:
        value = TypeAdapter(typ).validate_python(raw)
    except Exception as e:
        raise ConfigError(f"Invalid value '{raw}' for this key: {e}") from None
    # Enums (StrEnum is a str subclass) must be written as their value.
    if hasattr(value, "value") and not isinstance(value, str):
        return value.value
    return value


# --- tomlkit file editing ---------------------------------------------------


def _read_doc(path: Path):
    """Read a TOML file as a tomlkit document (empty if missing)."""
    if not path.exists():
        return tomlkit.document()
    with open(path, "rb") as f:
        return tomlkit.parse(f.read())


def _ensure_table(node, name):
    """Return the table at ``node[name]``, creating it if absent."""
    existing = node.get(name)
    if isinstance(existing, (tomlkit.items.Table, tomlkit.items.InlineTable)):
        return existing
    t = tomlkit.table()
    node[name] = t
    return t


def _set_in_doc(doc, parts: list[str], value) -> None:
    """Set ``parts`` (already under tool.vestibule) to ``value``."""
    vest = _ensure_table(_ensure_table(doc, "tool"), "vestibule")
    node = vest
    for p in parts[:-1]:
        node = _ensure_table(node, p)
    node[parts[-1]] = value


def _navigate(doc, parts: list[str]):
    """Return the node at ``parts`` (absolute, incl. tool/vestibule), else None."""
    node = doc
    try:
        for p in parts:
            node = node[p]
    except (KeyError, TypeError):
        return None
    return node


def _unset_in_doc(doc, parts: list[str]) -> bool:
    """Remove the node at ``parts`` (absolute). Returns True if removed."""
    parent = _navigate(doc, parts[:-1])
    if parent is None or parts[-1] not in parent:
        return False
    del parent[parts[-1]]
    return True


def _atomic_write(path: Path, doc) -> None:
    """Write the document atomically (temp file + os.replace)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".config.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            tomlkit.dump(doc, f)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# --- read-side helpers ------------------------------------------------------


def _get_value(cfg: Config, parts: list[str]) -> tuple[bool, Any]:
    """Navigate the merged Config; return (found, value)."""
    node = cfg
    for p in parts:
        if isinstance(node, BaseModel):
            node = getattr(node, p, None)
        elif isinstance(node, dict):
            if p not in node:
                return False, None
            node = node[p]
        else:
            return False, None
    return True, node


def _is_empty(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, bool):
        return False
    if isinstance(v, (int, float)):
        return False
    return v in ("", [], {})


def _format_value(v: Any) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


def _source_of(parts: list[str]) -> str:
    """Return the source layer ('project'/'user'/'default') for a key."""
    full = ["tool", "vestibule"] + parts
    if _navigate(_read_doc(_project_path()), full) is not None:
        return "project"
    if _navigate(_read_doc(_user_path()), full) is not None:
        return "user"
    return "default"


# --- commands ---------------------------------------------------------------


@config_app.command()
@_handle
def get(key: Annotated[str, typer.Argument(...)]) -> None:
    """Print the effective value of a config key."""
    parts = _parse_key(key)
    schemas = _plugin_schemas() if parts[0] == "plugins" else {}
    typ = _leaf_type(parts, schemas)
    if typ is None:
        raise ConfigError(f"Unknown config key '{key}'.")

    found, value = _get_value(Config.load(), parts)
    if not found:
        raise ConfigError(f"'{key}' is not set.")
    if _is_empty(value):
        typer.echo(f"'{key}' is set to an empty value.")
    else:
        typer.echo(_format_value(value))


@config_app.command()
@_handle
def set(
    key: Annotated[str, typer.Argument(...)],
    value: Annotated[str, typer.Argument(...)],
    user: Annotated[
        bool, typer.Option("--user", help="Write to ~/.vestibule/config.toml.")
    ] = False,
    file: Annotated[
        str | None, typer.Option("--file", help="Write to a specific config file.")
    ] = None,
) -> None:
    """Set a config key, coerced/validated against the schema."""
    parts = _parse_key(key)
    schemas = _plugin_schemas() if parts[0] == "plugins" else {}
    typ = _leaf_type(parts, schemas)
    if typ is None:
        raise ConfigError(f"Unknown config key '{key}'.")
    coerced = _coerce(typ, value)

    path = _write_target(user, file)
    doc = _read_doc(path)
    _set_in_doc(doc, parts, coerced)
    _atomic_write(path, doc)
    typer.echo(f"Set {key} = {_format_value(coerced)} in {path}")


@config_app.command()
@_handle
def unset(
    key: Annotated[str, typer.Argument(...)],
    section: Annotated[
        bool, typer.Option("--section", help="Remove a whole section rather than one key.")
    ] = False,
    user: Annotated[bool, typer.Option("--user", help="Edit ~/.vestibule/config.toml.")] = False,
    file: Annotated[str | None, typer.Option("--file", help="Edit a specific config file.")] = None,
) -> None:
    """Remove a config key (or section) from the target file."""
    parts = _parse_key(key)
    path = _write_target(user, file)
    doc = _read_doc(path)
    full = ["tool", "vestibule"] + parts
    if _unset_in_doc(doc, full):
        _atomic_write(path, doc)
        typer.echo(f"Removed {key} from {path}")
    else:
        typer.echo(f"'{key}' not present in {path}; no-op.")


def _enumerate_keys(cfg: Config, schemas: dict[str, type], include_defaults: bool):
    """Yield (parts, value, source) for display in ``list``."""
    items = []

    def add(parts, value, source):
        items.append((parts, value, source))

    for f in ("host", "port", "transport", "log_level"):
        add([f], getattr(cfg, f), _source_of([f]))
    add(["approval", "enabled"], cfg.approval.enabled, _source_of(["approval", "enabled"]))
    for tool, mode in cfg.approval.overrides.items():
        add(["approval", "overrides", tool], mode, _source_of(["approval", "overrides", tool]))
    for name, lim in cfg.rate_limits.items():
        add(["rate_limits", name], lim, _source_of(["rate_limits", name]))
    for pname, pconf in cfg.plugins.items():
        for fname, fval in pconf.items():
            add(["plugins", pname, fname], fval, _source_of(["plugins", pname, fname]))
    if include_defaults:
        for pname, schema in schemas.items():
            for fname, f in schema.model_fields.items():
                if fname not in cfg.plugins.get(pname, {}):
                    if f.is_required():  # no default, only settable
                        continue
                    add(
                        ["plugins", pname, fname],
                        f.get_default(call_default_factory=True),
                        "default",
                    )
    return items


@config_app.command("list")
@_handle
def list_config(
    all: Annotated[
        bool, typer.Option("--all", help="Include unset keys with their defaults.")
    ] = False,
) -> None:
    """List effective config, annotated with its source layer."""
    cfg = Config.load()
    schemas = _plugin_schemas() if all else {}

    typer.echo("Config sources:")
    for label, p in (("user", _user_path()), ("project", _project_path())):
        marker = "" if p.exists() else " (missing)"
        typer.echo(f"  {label}: {p}{marker}")
    typer.echo()

    for parts, value, source in _enumerate_keys(cfg, schemas, include_defaults=all):
        typer.echo(f"{PREFIX}{'.'.join(parts)} = {_format_value(value)}  ({source})")
