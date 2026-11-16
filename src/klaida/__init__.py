"""klaida: exceptions that document themselves."""

from .base import REGISTRY, DocumentedError, DuplicateCodeError, get_error
from .render import explain

__all__ = [
    "REGISTRY",
    "DocumentedError",
    "DuplicateCodeError",
    "explain",
    "get_error",
]
