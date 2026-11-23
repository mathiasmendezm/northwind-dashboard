"""End-to-end smoke test: run app.py headlessly and visit every page.

This doesn't assert on rendered content — it exists to catch the class of bug
unit tests miss entirely: a page that throws at runtime (KeyError, ZeroDivisionError,
a chart call with a bad argument) because Streamlit swallows exceptions into the
page instead of failing the test process. Without this, a broken page would only
surface when a person clicked into it.
"""

from pathlib import Path

from streamlit.testing.v1 import AppTest

# Absolute path: newer Streamlit resolves relative paths against this file, older
# versions against the working directory.
APP = str(Path(__file__).resolve().parent.parent / "app.py")


def test_every_page_renders_without_raising():
    at = AppTest.from_file(APP, default_timeout=30)
    at.run()
    assert not at.exception, f"Overview page raised: {at.exception}"

    radio = at.sidebar.radio[0]
    for option in radio.options:
        at = radio.set_value(option).run()
        assert not at.exception, f"Page '{option}' raised: {at.exception}"
