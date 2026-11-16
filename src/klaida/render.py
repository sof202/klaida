"""Render error classes to Markdown, HTML, an index, and llms.txt.

Output is deterministic (no timestamps) so `klaida check` can diff it.

"""

from __future__ import annotations

import inspect
import json
import re
from collections.abc import Sequence
from html import escape

from .base import DocumentedError, get_error

ErrorClass = type[DocumentedError]


def _details(cls: ErrorClass) -> str:
    return inspect.cleandoc(cls.__dict__.get("__doc__") or "")


def _title(cls: ErrorClass) -> str:
    return f"{cls.code}: {cls.summary}"


# - markdown ------------------------------------------------------------------
def markdown_page(cls: ErrorClass) -> str:
    """Convert error into a markdown page."""
    parts = [f"# {_title(cls)}", ""]
    parts.append(f"- **Code:** `{cls.code}`")
    if cls.docs_url():
        parts.append(f"- **Page:** {cls.docs_url()}")
    for heading, body in (
        ("Cause", cls.cause),
        ("Fix", cls.fix),
        ("Details", _details(cls)),
    ):
        if body:
            parts += ["", f"## {heading}", "", body.strip()]
    return "\n".join(parts) + "\n"


def index_markdown(classes: Sequence[ErrorClass], title: str) -> str:
    """Create a toc for markdown pages."""
    lines = [f"# {title}", ""]
    lines += [
        f"- [{c.code}]({c.code}.md): {c.summary}" for c in _sorted(classes)
    ]
    return "\n".join(lines) + "\n"


def llms_txt(classes: Sequence[ErrorClass], title: str) -> str:
    """Context for llms.txt describing how llms should interpret errors."""
    lines = [
        f"# {title}",
        "",
        "> One page per error. Each page gives the cause and the fix for that "
        "> error code.",
        "",
        "## Errors",
        "",
    ]
    for c in _sorted(classes):
        href = (
            f"{c.docs_base.rstrip('/')}/{c.code}.md"
            if c.docs_base
            else f"{c.code}.md"
        )
        note = f": {c.cause}" if c.cause else ""
        lines.append(f"- [{_title(c)}]({href}){note}")
    return "\n".join(lines) + "\n"


# - html ----------------------------------------------------------------------
_CSS = """
:root {
  --bg: #fff;
  --fg: #1a1a1a;
  --muted: #5c5c5c;
  --code: #f3f3f3;
  --accent: #0b5fd7;
}

@media (prefers-color-scheme: dark) {
  :root {
    --bg: #161616;
    --fg: #e8e8e8;
    --muted: #a0a0a0;
    --code: #242424;
    --accent: #7ab0ff;
  }
}

body {
  margin: 0;
  background: var(--bg);
  color: var(--fg);
  font: 17px/1.6 system-ui, sans-serif;
}

main {
  max-width: 46rem;
  margin: 0 auto;
  padding: 2rem 1rem;
}

a {
  color: var(--accent);
}

.crumb {
  color: var(--muted);
  font-size: .9rem;
}

h1 {
  font-size: 1.6rem;
  line-height: 1.25;
}

h2 {
  font-size: 1.2rem;
  margin-top: 2rem;
}

code,
pre {
  background: var(--code);
  border-radius: 4px;
  font-size: .92em;
}

code {
  padding: .1em .3em;
}

pre {
  padding: .8rem 1rem;
  overflow-x: auto;
}

pre code {
  padding: 0;
}
"""


def _inline(text: str) -> str:
    out = []
    for piece in re.split(r"(`[^`]+`)", text):
        if len(piece) > 2 and piece[0] == piece[-1] == "`":
            out.append(f"<code>{escape(piece[1:-1])}</code>")
        else:
            out.append(escape(piece))
    return "".join(out)


def _body_html(text: str) -> str:
    """Tiny Markdown subset.

    Includes: paragraphs, fenced code, `inline code`, # headings.

    """
    html: list[str] = []
    paragraph: list[str] = []
    code: list[str] = []
    in_code = False

    def flush() -> None:
        if paragraph:
            html.append(f"<p>{_inline(' '.join(paragraph))}</p>")
            paragraph.clear()

    for line in text.splitlines():
        if line.strip().startswith("```"):
            if in_code:
                html.append(
                    f"<pre><code>{escape(chr(10).join(code))}</code></pre>"
                )
                code.clear()
            else:
                flush()
            in_code = not in_code
        elif in_code:
            code.append(line)
        elif m := re.match(r"#{1,6}\s+(.*)", line):
            flush()
            html.append(f"<h3>{_inline(m.group(1))}</h3>")
        elif line.strip():
            paragraph.append(line.strip())
        else:
            flush()
    if in_code and code:
        html.append(f"<pre><code>{escape(chr(10).join(code))}</code></pre>")
    flush()
    return "\n".join(html)


def _page(
    title: str, description: str, body: str, head_extra: str = ""
) -> str:
    return (
        "<!doctype html>\n"
        '<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        f"<title>{escape(title)}</title>\n"
        f'<meta name="description" content="{escape(description, quote=True)}">\n'  # noqa: E501
        f"{head_extra}<style>{_CSS}</style>\n</head>\n"
        f"<body>\n<main>\n{body}\n</main>\n</body>\n</html>\n"
    )


def html_page(cls: ErrorClass, project_title: str) -> str:
    """Convert error into html page (mirrors `markdown_page`)."""
    desc = " ".join(
        x for x in (cls.cause, f"Fix: {cls.fix}" if cls.fix else "") if x
    )
    ld = {
        "@context": "https://schema.org",
        "@type": "TechArticle",
        "headline": _title(cls),
        "identifier": cls.code,
        "description": desc or cls.summary,
    }
    if cls.docs_url():
        ld["url"] = cls.docs_url()
    head = (
        '<link rel="alternate" type="text/markdown"'
        f'href="{escape(cls.code)}.md">\n'
    )
    if cls.docs_url():
        head += (
            '<link rel="canonical" '
            f'href="{escape(cls.docs_url(), quote=True)}">\n'
        )
    head += (
        '<script type="application/ld+json">'
        + json.dumps(ld, ensure_ascii=False).replace("</", "<\\/")
        + "</script>\n"
    )
    body = [
        '<p class="crumb"><a href="index.html">'
        f"{escape(project_title)}</a></p>",
        f"<h1>{escape(_title(cls))}</h1>",
    ]
    for heading, text in (
        ("Cause", cls.cause),
        ("Fix", cls.fix),
        ("Details", _details(cls)),
    ):
        if text:
            body.append(
                f"<section>\n<h2>{heading}</h2>\n{_body_html(text)}\n</section>"
            )
    return _page(_title(cls), desc or cls.summary, "\n".join(body), head)


def index_html(classes: Sequence[ErrorClass], title: str) -> str:
    """Create a toc for html pages (mirrors `index_markdown`)."""
    items = "\n".join(
        f'<li><a href="{escape(c.code)}.html">{escape(c.code)}</a>: '
        f"{escape(c.summary)}</li>"
        for c in _sorted(classes)
    )
    body = f"<h1>{escape(title)}</h1>\n<ul>\n{items}\n</ul>"
    return _page(title, f"Reference for every error raised by {title}.", body)


# - misc ----------------------------------------------------------------------
def _sorted(classes: Sequence[ErrorClass]) -> list[ErrorClass]:
    return sorted(classes, key=lambda c: c.code.casefold())


def explain(code: str) -> str:
    """Markdown documentation for one registered error code."""
    cls = get_error(code)
    if cls is None:
        raise KeyError(f"Unknown error code: {code!r}")
    return markdown_page(cls)
