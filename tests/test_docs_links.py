"""Relative links in the Markdown documentation must resolve."""
import importlib.util
import pathlib

_spec = importlib.util.spec_from_file_location("check_links", pathlib.Path(__file__).resolve().parent.parent / "scripts" / "check_links.py")
check_links = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_links)


def test_no_broken_relative_links():
    assert check_links.broken_links(check_links.tracked_markdown()) == []
