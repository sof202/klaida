"""klaida cli."""

from __future__ import annotations

import argparse
import importlib
import sys
from collections.abc import Sequence
from pathlib import Path

from . import render
from .base import REGISTRY, get_error, problems
from .config import Config, ConfigError, load_config


def load_classes(cfg: Config) -> list[type]:
    """Import the configured modules and return the error classes."""
    if not cfg.modules:
        raise ConfigError(
            "No modules configured. Set `modules` under [tool.klaida]."
        )
    for p in (cfg.root, cfg.root / "src"):
        if p.is_dir() and str(p) not in sys.path:
            sys.path.insert(0, str(p))
    for name in cfg.modules:
        importlib.import_module(name)
    wanted = [
        c
        for c in REGISTRY.values()
        if any(
            c.__module__ == m or c.__module__.startswith(m + ".")
            for m in cfg.modules
        )
    ]
    return sorted(wanted, key=lambda c: c.code.casefold())


def generate(classes: Sequence[type], cfg: Config) -> dict[Path, str]:
    """Every file `build` would write, as {path: content}."""
    out: dict[Path, str] = {}
    for c in classes:
        out[cfg.output / f"{c.code}.md"] = render.markdown_page(c)
        out[cfg.output / f"{c.code}.html"] = render.html_page(c, cfg.title)
    out[cfg.output / "index.md"] = render.index_markdown(classes, cfg.title)
    out[cfg.output / "index.html"] = render.index_html(classes, cfg.title)
    if cfg.llms_txt:
        out[cfg.llms_txt] = render.llms_txt(classes, cfg.title)
    return out


def _build(cfg: Config) -> int:
    files = generate(load_classes(cfg), cfg)
    for path, content in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    print(f"Wrote {len(files)} files to {cfg.output}")
    return 0


def _check(cfg: Config) -> int:
    classes = load_classes(cfg)  # duplicate codes already raised on import
    issues: list[str] = []
    for c in classes:
        issues += [f"{c.code} ({c.__qualname__}): {p}" for p in problems(c)]
    for path, content in generate(classes, cfg).items():
        rel = path.relative_to(cfg.root)
        if not path.is_file():
            issues.append(f"{rel}: missing (run `klaida build`)")
        elif path.read_text(encoding="utf-8") != content:
            issues.append(f"{rel}: out of date (run `klaida build`)")
    for i in issues:
        print(i, file=sys.stderr)
    if not issues:
        print(f"OK: {len(classes)} errors documented")
    return 1 if issues else 0


def _explain(cfg: Config, code: str) -> int:
    load_classes(cfg)
    cls = get_error(code)
    if cls is None:
        known = ", ".join(c.code for c in REGISTRY.values()) or "none"
        print(
            f"Unknown error code {code!r}. Known codes: {known}",
            file=sys.stderr,
        )
        return 1
    print(render.markdown_page(cls), end="")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for cli."""
    parser = argparse.ArgumentParser(prog="klaida", description=__doc__)
    parser.add_argument(
        "--config", help="path to pyproject.toml (default: ./pyproject.toml)"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser(
        "build", help="write one page per error, plus index and llms.txt"
    )
    sub.add_parser(
        "check", help="verify the catalog and that generated pages are current"
    )
    ex = sub.add_parser("explain", help="print the docs for one error code")
    ex.add_argument("code")
    args = parser.parse_args(argv)
    try:
        cfg = load_config(args.config)
        if args.command == "build":
            return _build(cfg)
        if args.command == "check":
            return _check(cfg)
        return _explain(cfg, args.code)
    except (ConfigError, ImportError, TypeError) as exc:
        print(f"klaida: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
