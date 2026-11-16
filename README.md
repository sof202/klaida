# klaida

The problem: It doesn't matter how good your errors and documentation are. Most
users just cannot be bothered to read it. Instead of spending 5 minutes reading
documentation, they'd rather go in endless circles with an LLM chatbot (which
often doesn't have enough context to solve the core issue).

Klaida is a simple exception framework (with a complementary cli tool) where
you get:

- a **short runtime message**: code, summary, optional specifics, and a link
- a **docs page per error** (HTML + Markdown) with the cause, the fix and any
  notes
- an **index** and an **`llms.txt`**
- a **CI check** that the catalog and the generated pages haven't drifted

The idea: users paste the error into a chatbot. The link travels with it, and a
chatbot that can browse reads the *real* fix instead of guessing one.

## Use it in a project

```python
# mylib/errors.py
from klaida import DocumentedError

class MylibError(DocumentedError):
    docs_base = "https://you.github.io/mylib/errors"

class ShapeMismatch(MylibError):
    """Free-text notes.

    This becomes the "Details" section 
    (Markdown: `code`, ``` blocks, # headings).

    """
    code = "E1001"
    summary = "Input arrays have different lengths"
    cause = "x and y came from different sources, or only one was filtered."
    fix = "Check len(x) == len(y) before calling fit()."
    hint = "len(x) must equal len(y)" # optional, <= 80 chars
```

```python
raise ShapeMismatch(f"len(x)={len(x)}, len(y)={len(y)}")
```

```
[E1001] Input arrays have different lengths (len(x)=3, len(y)=5)
Hint: len(x) must equal len(y)
See: https://you.github.io/mylib/errors/E1001.html
```

Build config goes in your project's `pyproject.toml` (CLI only; `docs_base` stays
in code because an installed wheel has no pyproject):

```toml
[tool.klaida]
modules = ["mylib.errors"]     # imported to find error classes
output = "docs/errors"         # default
title = "mylib error reference"
llms_txt = "docs/llms.txt"     # default: <output>/llms.txt; false to disable
```

## CLI

```
klaida build            # write pages, index, llms.txt
klaida check            # CI: duplicate codes, missing cause/fix/docs_base, stale pages
klaida explain E1001    # print one page in the terminal
```

Want `mylib explain E1001` too? `from klaida import explain` and print
`explain(code)`.

## Publishing

`example/.github/workflows/docs.yml` runs `check` and deploys `docs/` to GitHub
Pages. Pages are static files: `E1001.html`, `E1001.md`, `index.*`, `llms.txt`.
If you build the rest of your site with MkDocs/Sphinx, point `output` inside
that site's source folder instead.

## Design notes

- Each HTML page has the exact summary in `<title>` and `<h1>`, a
  `<link rel="alternate" type="text/markdown">` to the `.md`, and JSON-LD.
- Output is deterministic, so `check` can diff it against what's on disk.
- Codes are case-insensitive for lookup and must be unique across everything
  imported.
- Generated pages for *deleted* errors are not removed automatically; delete
  the file.

## Develop

```
pip install -e ".[dev]" && pytest
cd example && klaida build   # see generated output in example/docs/errors
```
