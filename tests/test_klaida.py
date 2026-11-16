"""Tests for klaida."""

import json
import re
import sys
import textwrap
from collections.abc import Generator
from pathlib import Path

import pytest

from klaida import (
    REGISTRY,
    DocumentedError,
    DuplicateCodeError,
    explain,
    get_error,
    render,
)
from klaida.cli import main


@pytest.fixture(autouse=True)
def clean_registry() -> Generator[None, None, None]:
    """Snapshot and restore the klaida registry around each test."""
    snapshot = dict(REGISTRY)
    yield
    REGISTRY.clear()
    REGISTRY.update(snapshot)


def make() -> tuple[type[DocumentedError], type[DocumentedError]]:
    """Create an example base and concrete documented exception class."""

    class Base(DocumentedError):
        docs_base = "https://example.org/errors/"

    class Boom(Base):
        """Longer notes with `code`.

        ```
        raise Boom()
        ```
        """

        code = "T1"
        summary = "Something broke"
        cause = "Because."
        fix = "Do the thing."

    return Base, Boom


def test_message_is_short_and_links_to_docs() -> None:
    """Should format a concise message with a docs link while omitting details.

    Given:
        A documented error subclass with a summary, cause, fix, and docs base.
    When:
        The exception is instantiated with context and converted to a string.
    Then:
        The message contains the code, summary, context, and docs URL, without
        cause or fix.

    """
    _, Boom = make()
    msg = str(Boom("x=1"))
    assert (
        msg
        == "[T1] Something broke (x=1)\nSee: https://example.org/errors/T1.html"
    )
    assert "Because" not in msg and "Do the thing" not in msg


def test_hint_shown_when_set() -> None:
    """Should include the hint in the formatted error message when defined.

    Given:
        A documented error subclass with a hint attribute set.
    When:
        The exception is instantiated and converted to a string.
    Then:
        The formatted message includes the hint text.

    """
    Base, _ = make()

    class Hinted(Base):
        code = "T2"
        summary = "s"
        hint = "short hint"

    assert "Hint: short hint" in str(Hinted())


def test_no_docs_base_omits_link() -> None:
    """Should omit the documentation link when no docs base is configured.

    Given:
        A documented error subclass without a docs_base attribute.
    When:
        The exception is instantiated and converted to a string.
    Then:
        The message contains only the error code and summary.

    """

    class Plain(DocumentedError):
        code = "T3"
        summary = "s"

    assert str(Plain()) == "[T3] s"


def test_base_and_intermediate_not_raisable_or_registered() -> None:
    """Should prevent instantiating base and intermediate error classes.

    Given:
        DocumentedError and an intermediate subclass without a code or summary.
    When:
        Attempting to instantiate either class and inspecting the registry.
    Then:
        TypeError is raised for both and only concrete errors are registered.

    """
    Base, _ = make()
    with pytest.raises(TypeError):
        DocumentedError()
    with pytest.raises(TypeError):
        Base()
    assert "t1" in REGISTRY and len(REGISTRY) == 1


def test_duplicate_code_rejected_case_insensitively() -> None:
    """Should reject duplicate error codes regardless of letter case.

    Given:
        An error already registered with code 'T1'.
    When:
        A new error class is defined with code 't1'.
    Then:
        DuplicateCodeError is raised.

    """
    make()
    with pytest.raises(DuplicateCodeError):

        class Other(DocumentedError):
            code = "t1"
            summary = "s"


def test_bad_code_and_missing_summary_rejected() -> None:
    """Should reject error classes with invalid codes or missing summaries.

    Given:
        Error subclasses with whitespace in the code or without a summary
        attribute.
    When:
        The subclasses are defined.
    Then:
        TypeError is raised in both cases.

    """
    with pytest.raises(TypeError):

        class A(DocumentedError):
            code = "has space"
            summary = "s"

    with pytest.raises(TypeError):

        class B(DocumentedError):
            code = "T9"


def test_pickle_roundtrip() -> None:
    """Should preserve initialization arguments during pickle serialization.

    Given:
        An instantiated documented error with a message argument.
    When:
        __reduce__ is called on the exception instance.
    Then:
        The serialized state contains the original argument tuple.

    """
    _, Boom = make()
    import klaida.base  # noqa: F401

    err = Boom("d")
    assert err.__reduce__()[1] == ("d",)


def test_lookup_case_insensitive() -> None:
    """Should retrieve and explain registered errors case-insensitively.

    Given:
        An error registered under code 'T1'.
    When:
        get_error and explain are called with lowercase and uppercase codes.
    Then:
        The matching error class and formatted explanation are returned.

    """
    _, Boom = make()
    assert get_error("t1") is Boom
    assert "# T1: Something broke" in explain("T1")


def test_markdown_and_html_pages() -> None:
    """Should render complete Markdown and HTML pages for an error.

    Given:
        A documented error with summary, cause, fix, and docstring notes.
    When:
        render.markdown_page and render.html_page are called.
    Then:
        Both outputs contain the expected headings, code blocks, links, and
        JSON-LD metadata.

    """
    _, Boom = make()
    md = render.markdown_page(Boom)
    assert (
        md.startswith("# T1: Something broke")
        and "## Fix" in md
        and "## Details" in md
    )
    html = render.html_page(Boom, "Proj")
    assert "<title>T1: Something broke</title>" in html
    assert "<h1>T1: Something broke</h1>" in html
    assert 'href="T1.md"' in html
    assert "<pre><code>raise Boom()</code></pre>" in html

    ld_search = re.search(
        r'<script type="application/ld\+json">(.*?)</script>', html
    )
    assert ld_search is not None
    ld = ld_search.group(1)
    assert json.loads(ld)["identifier"] == "T1"


def test_html_escapes_content() -> None:
    """Should HTML-escape untrusted error fields to prevent script injection.

    Given:
        A documented error containing raw HTML and closing script tags in its
        fields.
    When:
        render.html_page is called to generate the HTML page.
    Then:
        Malicious tags are escaped outside the JSON-LD script block.

    """

    class Evil(DocumentedError):
        code = "T4"
        summary = "<script>alert(1)</script>"
        cause = "a </script> b"

    html = render.html_page(Evil, "P")
    outside = re.sub(
        r'<script type="application/ld\+json">.*?</script>',
        "",
        html,
        flags=re.S,
    )
    assert (
        "<script>alert(1)" not in outside
    )  # escaped in the page body and <title>
    assert (
        html.count("</script>") == 1
    )  # only the JSON-LD closer (inner ones are escaped)


def test_llms_txt() -> None:
    """Should generate an llms.txt index entry linking to the error's md page.

    Given:
        A list containing a documented error with a docs_base.
    When:
        render.llms_txt is called.
    Then:
        The output includes a Markdown link with the error's code, summary,
        URL, and cause.

    """
    _, Boom = make()
    txt = render.llms_txt([Boom], "Proj")
    assert (
        "- [T1: Something broke](https://example.org/errors/T1.md): Because."
        in txt
    )


@pytest.fixture
def project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[Path, None, None]:
    """Create a temporary project directory with config and error module."""
    (tmp_path / "pyproject.toml").write_text(
        '[tool.klaida]\nmodules = ["cli_demo_errors"]\ntitle = "Demo"\n'
    )
    (tmp_path / "cli_demo_errors.py").write_text(
        textwrap.dedent(
            """
            from klaida import DocumentedError

            class E(DocumentedError):
                docs_base = "https://example.org/e"

            class One(E):
                code = "C1"
                summary = "one"
                cause = "c"
                fix = "f"
            """
        )
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    yield tmp_path
    sys.modules.pop("cli_demo_errors", None)


def test_cli_build_check_explain(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Should support building, validating, and explaining errors via the CLI.

    Given:
        A configured project directory containing a valid error module.
    When:
        The CLI commands check, build, and explain are executed in sequence.
    Then:
        Expected documentation files are generated, drift is detected, and
        errors are explained.

    """
    cfg = ["--config", str(project / "pyproject.toml")]
    assert main(cfg + ["check"]) == 1  # nothing built yet
    assert main(cfg + ["build"]) == 0
    out = project / "docs" / "errors"
    assert {p.name for p in out.iterdir()} == {
        "C1.md",
        "C1.html",
        "index.md",
        "index.html",
        "llms.txt",
    }
    assert main(cfg + ["check"]) == 0
    (out / "C1.md").write_text("stale")
    assert main(cfg + ["check"]) == 1
    capsys.readouterr()
    assert main(cfg + ["explain", "c1"]) == 0
    assert "# C1: one" in capsys.readouterr().out
    assert main(cfg + ["explain", "nope"]) == 1


def test_check_flags_missing_fields(project: Path) -> None:
    """Should fail the CLI check command when errors lack required fields.

    Given:
        A project error module defining an error without cause or fix
        attributes.
    When:
        The CLI check command is invoked.
    Then:
        The command exits with a non-zero status code of 1.

    """
    (project / "cli_demo_errors.py").write_text(
        textwrap.dedent(
            """
            from klaida import DocumentedError

            class Two(DocumentedError):
                code = "C2"
                summary = "two"
            """
        )
    )
    assert main(["--config", str(project / "pyproject.toml"), "check"]) == 1
