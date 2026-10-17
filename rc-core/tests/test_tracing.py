"""Tests for tools.tracing — no real feenion exporter."""

import importlib

import pytest

from tools import tracing as tr


def test_noop_when_disabled(monkeypatch):
    monkeypatch.setattr(tr, "_ENABLED", False)
    with tr.span("anything", a=1):
        pass


def test_span_records_attrs_when_enabled(monkeypatch):
    """Fake feenion.span that captures its kwargs."""
    captured = {}

    class FakeSpan:
        def __init__(self, name, attributes=None):
            self.name = name
            self.attributes = attributes

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class FakeFeenion:
        @staticmethod
        def span(name, *, attributes=None):
            captured["name"] = name
            captured["attrs"] = attributes
            return FakeSpan(name, attributes=attributes)

    import sys
    fake_mod = type(sys)("feenion")
    fake_mod.span = FakeFeenion.span
    monkeypatch.setitem(sys.modules, "feenion", fake_mod)

    monkeypatch.setattr(tr, "_ENABLED", True)
    with tr.span("node.x", a=1, b="two"):
        pass

    assert captured["name"] == "node.x"
    assert captured["attrs"] == {"a": 1, "b": "two"}


def test_init_returns_false_on_failure(monkeypatch):
    """If feenion import or configure raises, init_tracing returns False."""
    import sys

    class BrokenFeenion:
        @staticmethod
        def configure(**kwargs):
            raise RuntimeError("configure failed")

    fake_mod = type(sys)("feenion")
    fake_mod.configure = BrokenFeenion.configure
    monkeypatch.setitem(sys.modules, "feenion", fake_mod)
    monkeypatch.setattr(tr, "_ENABLED", False)

    assert tr.init_tracing() is False
    assert tr._ENABLED is False