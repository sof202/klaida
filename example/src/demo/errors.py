"""A demonstration of defining klaida errors."""

from klaida import DocumentedError


class DemoError(DocumentedError):
    """Base error class for library."""

    docs_base = "https://yourname.github.io/demo/errors"


class ShapeMismatch(DemoError):
    """Raised at the start of `fit()`, before any work is done.

    ```python
    fit([1, 2, 3], [1, 2])   # raises E1001
    ```

    It is most often caused by filtering `x` but not `y`.
    """

    code = "E1001"
    summary = "Input arrays have different lengths"
    cause = "x and y came from different sources, or only one of them was filtered."
    fix = "Check that len(x) == len(y) before calling fit()."
    hint = "len(x) must equal len(y)"


class ConfigMissing(DemoError):
    code = "E1002"
    summary = "Config file not found"
    cause = "The path passed to load() does not exist, or is relative to a different directory."
    fix = "Pass an absolute path, or run from the directory that contains the file."
