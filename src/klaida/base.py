"""The abstract exception base class and the global error registry."""

from __future__ import annotations

import re
from typing import ClassVar

REGISTRY: dict[str, type[DocumentedError]] = {}
"""Registered error classes, keyed by `code.casefold()`."""

_CODE_RE = re.compile(r"^[A-Za-z0-9_-]+$")
HINT_MAX = 80


class DuplicateCodeError(TypeError):
    """Two different classes tried to register the same error code."""


class DocumentedError(Exception):
    """Base class for exceptions that have a page in the generated docs.

    Subclass once per project to set `docs_base`, then subclass that per
    error::

        class MylibError(DocumentedError):
            docs_base = "https://me.github.io/mylib/errors"

        class ShapeMismatch(MylibError):
            code = "E1001"
            summary = "Input arrays have different lengths"
            cause = "x and y came from different sources."
            fix = "Check len(x) == len(y) before calling fit()."

    The class docstring becomes the free-text "Details" section of the page.
    Only `code` and `summary` are shown in the runtime message (plus the
    optional `hint`); `cause` and `fix` live on the docs page.

    """

    code: ClassVar[str] = ""
    summary: ClassVar[str] = ""
    cause: ClassVar[str] = ""
    fix: ClassVar[str] = ""
    hint: ClassVar[str] = ""  # optional, <= 80 chars, shown in the message
    docs_base: ClassVar[str] = ""

    def __init_subclass__(cls, **kwargs) -> None:
        """Register subclass for klaida."""
        super().__init_subclass__(**kwargs)
        if "code" not in cls.__dict__:
            return  # intermediate base class (e.g. the per-project one)
        if not _CODE_RE.match(cls.code):
            raise TypeError(
                f"{cls.__qualname__}: code {cls.code!r} must be non-empty and use "
                "only letters, digits, '-' and '_' (it becomes a URL path)."
            )
        if not cls.summary:
            raise TypeError(
                f"{cls.__qualname__}: a non-empty `summary` is required."
            )
        key = cls.code.casefold()
        existing = REGISTRY.get(key)
        if existing is not None and (
            existing.__module__,
            existing.__qualname__,
        ) != (
            cls.__module__,
            cls.__qualname__,
        ):
            raise DuplicateCodeError(
                f"Error code {cls.code!r} is used by both "
                f"{existing.__module__}.{existing.__qualname__} and "
                f"{cls.__module__}.{cls.__qualname__}."
            )
        REGISTRY[key] = cls

    def __init__(self, detail: str = "") -> None:
        if not self.code:
            raise TypeError(
                f"{type(self).__name__} has no `code`; subclass it and set "
                "`code` and `summary` before raising."
            )
        self.detail = str(detail)
        super().__init__(self._render())

    def __reduce__(
        self,
    ) -> tuple[type, tuple[str]]:
        """Keep pickling (multiprocessing etc.) from re-rendering."""
        return (type(self), (self.detail,))

    @classmethod
    def docs_url(cls) -> str:
        """URL of this error's HTML page, or '' if `docs_base` is unset."""
        if not cls.docs_base:
            return ""
        return f"{cls.docs_base.rstrip('/')}/{cls.code}.html"

    def _render(self) -> str:
        head = f"[{self.code}] {self.summary}"
        if self.detail:
            head += f" ({self.detail})"
        lines = [head]
        if self.hint:
            lines.append(f"Hint: {self.hint}")
        url = self.docs_url()
        if url:
            lines.append(f"See: {url}")
        return "\n".join(lines)


def get_error(code: str) -> type[DocumentedError] | None:
    """Look up a registered error class by code (case-insensitive)."""
    return REGISTRY.get(code.casefold())


def problems(cls: type[DocumentedError]) -> list[str]:
    """Quality problems with an error class, for `klaida check`."""
    out = []
    if not cls.cause:
        out.append("missing `cause`")
    if not cls.fix:
        out.append("missing `fix`")
    if not cls.docs_base:
        out.append("missing `docs_base` (set it on your project's base class)")
    if len(cls.hint) > HINT_MAX:
        out.append(f"`hint` is {len(cls.hint)} chars (max {HINT_MAX})")
    return out
