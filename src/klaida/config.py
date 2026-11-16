"""Build-time configuration, read from `[tool.klaida]` in pyproject.toml.

Only the CLI uses this. Anything needed at runtime (`docs_base`) lives on
the exception classes, because an installed wheel has no pyproject.toml.

"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib

KNOWN_KEYS = {"modules", "output", "title", "llms_txt"}


class ConfigError(Exception):
    """Exception raised when a config parsing error occurs."""

    pass


@dataclass
class Config:
    """Configuration for klaida."""

    root: Path
    modules: list[str] = field(default_factory=list)
    output: Path = Path("docs/errors")
    title: str = "Error reference"
    llms_txt: Path | None = None


def load_config(path: str | Path | None = None) -> Config:
    """Attempt to parse config from pyproject.toml."""
    pyproject = Path(path) if path else Path.cwd() / "pyproject.toml"
    root = pyproject.resolve().parent
    table = {}
    if pyproject.is_file():
        with pyproject.open("rb") as fh:
            table = tomllib.load(fh).get("tool", {}).get("klaida", {})
    unknown = set(table) - KNOWN_KEYS
    if unknown:
        raise ConfigError(
            f"Unknown [tool.klaida] keys: {', '.join(sorted(unknown))}"
        )

    output = root / table.get("output", "docs/errors")
    llms = table.get(
        "llms_txt", True
    )  # true = <output>/llms.txt, false = off, str = path
    if llms is False:
        llms_path = None
    elif llms is True:
        llms_path = output / "llms.txt"
    else:
        llms_path = root / llms
    modules = table.get("modules", [])
    if not isinstance(modules, list):
        raise ConfigError(
            "[tool.klaida] modules must be a list of module names"
        )
    return Config(
        root=root,
        modules=modules,
        output=output,
        title=table.get("title", "Error reference"),
        llms_txt=llms_path,
    )
