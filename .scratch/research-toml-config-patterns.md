# Research: TOML Configuration Patterns

## Summary

**Recommended approach for [Pp]ortcullis:**
- Config file: `.portcullis/config.toml` (project) + `~/.portcullis/config.toml` (user global)
- TOML namespace: `[tool.portcullis]` for server settings, `[tool.portcullis.plugins]` for plugin config
- Merge order: CLI args > project config > user config > defaults
- Use stdlib `tomllib` (Python 3.11+)

---

## pytest Configuration Patterns

**Source:** [pytest documentation](https://docs.pytest.org/en/stable/reference/customize.html)

### File Locations (precedence order)
1. `pytest.toml` / `.pytest.toml` (pytest 9.0+)
2. `pytest.ini` / `.pytest.ini`
3. `pyproject.toml` (with `[tool.pytest]` or `[tool.pytest.ini_options]`)
4. `tox.ini` (with `[pytest]` section)
5. `setup.cfg` (with `[tool:pytest]` section)

### TOML Structure (pytest 9.0+ native)
```toml
[tool.pytest]
minversion = "9.0"
addopts = ["-ra", "-q"]
testpaths = ["tests", "integration"]
```

### Plugin Configuration
Plugins are configured via entry points in `pyproject.toml`:
```toml
[project.entry-points.pytest11]
myproject = "myproject.pluginmodule"
```

Plugins can add their own config sections under `[tool.pytest]`.

---

## Black Configuration

**Source:** [Black documentation](https://black.readthedocs.io/en/stable/guides/using_black_with_other_tools.html)

### File Location
- `pyproject.toml` with `[tool.black]` section
- Can also use `.black.toml`

### TOML Structure
```toml
[tool.black]
line-length = 88
target-version = ["py310"]
include = '\.pyi?$'
```

---

## mypy Configuration

**Source:** [mypy documentation](https://mypy.readthedocs.io/en/latest/config_file.html)

### File Location
- `pyproject.toml` with `[tool.mypy]` section
- Also supports `mypy.ini`, `.mypy.ini`

### TOML Structure
```toml
[tool.mypy]
python_version = "3.10"
strict = true
warn_return_any = true
ignore_missing_imports = true

[[tool.mypy.overrides]]
module = ["tests.*"]
ignore_missing_imports = true
```

### Plugin Configuration
mypy plugins are listed in the config:
```toml
[tool.mypy]
plugins = ["pydantic.mypy", "some_other_plugin"]
```

---

## flake8 Configuration

**Source:** [flake8 documentation](https://flake8.pycqa.org/en/latest/user/configuration.html)

### File Location
- **Does NOT natively support `pyproject.toml`**
- Uses `.flake8`, `setup.cfg`, or `tox.ini`
- Can use `flake8-pyproject` plugin to enable `pyproject.toml` support

### setup.cfg Structure
```ini
[flake8]
max-line-length = 88
extend-ignore = E203, E701
exclude = .git,__pycache__,build,dist
```

---

## Modern CLI Tools (Cyclopts, Clevis)

**Source:** [Cyclopts docs](https://cyclopts.readthedocs.io/en/stable/config_file.html), [Clevis PyPI](https://pypi.org/project/clevis/)

### Cyclopts Pattern
```python
app = App(
    name="my-cli",
    config=cyclopts.config.Toml(
        "pyproject.toml",
        root_keys=["tool", "my-cli"],
        search_parents=True,
    ),
)
```

### Config Priority
1. CLI arguments
2. Environment variables
3. Project TOML (`./pyproject.toml`)
4. User TOML (`~/.myapp.toml`)
5. Python defaults

### TOML Structure
```toml
[tool.my-cli]
verbose = true
output-format = "json"

[tool.my-cli.subcommand]
option = "value"
```

---

## Key Patterns for [Pp]ortcullis

### 1. Config File Locations

| Priority | Location | Purpose |
|----------|----------|---------|
| 1 (highest) | CLI `--config=<path>` | Override everything |
| 2 | `.portcullis/config.toml` | Project-specific settings |
| 3 | `~/.portcullis/config.toml` | User defaults |
| 4 (lowest) | Built-in defaults | Fallback values |

### 2. TOML Namespace Structure

```toml
# Server settings
[tool.portcullis]
host = "localhost"
port = 8080
transport = "stdio"  # or "http-sse"
log-level = "info"

# Plugin configuration
[tool.portcullis.plugins.email]
enabled = true
default_recipient = "admin@example.com"

[tool.portcullis.plugins.calendar]
enabled = true
default_timezone = "UTC"
```

### 3. Plugin Config Pattern

Plugins get their own namespaced section:
```toml
[tool.portcullis.plugins.<plugin-name>]
key = "value"
```

### 4. Secrets Separation

**TOML is NOT for secrets.** Secrets stay in `.env`:
```bash
# .env (not committed to git)
EMAIL_SMTP_HOST=smtp.gmail.com
EMAIL_SMTP_PASSWORD=app-password-here
```

TOML is for non-secret configuration only.

---

## Sources

1. [pytest Configuration](https://docs.pytest.org/en/stable/reference/customize.html)
2. [pytest Writing Plugins](https://docs.pytest.org/en/stable/how-to/writing_plugins.html)
3. [Black Configuration](https://black.readthedocs.io/en/stable/guides/using_black_with_other_tools.html)
4. [mypy Configuration](https://mypy.readthedocs.io/en/latest/config_file.html)
5. [flake8 Configuration](https://flake8.pycqa.org/en/latest/user/configuration.html)
6. [Cyclopts Config](https://cyclopts.readthedocs.io/en/stable/config_file.html)
7. [Clevis PyPI](https://pypi.org/project/clevis/)
