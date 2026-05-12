import importlib
import subprocess
from unittest.mock import MagicMock

from doc_preprocessor.deps import DependencyRegistry, get_installed_version, install_package


def test_install_package_calls_invalidate_caches_on_success(monkeypatch):
    proc_mock = MagicMock()
    proc_mock.returncode = 0
    proc_mock.stdout = "installed"
    proc_mock.stderr = ""

    invalidate_called = []
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: proc_mock)
    monkeypatch.setattr(importlib, "invalidate_caches", lambda: invalidate_called.append(True))

    registry = DependencyRegistry()
    event = install_package("markitdown", "test reason", dry_run=False, registry=registry)

    assert event.success
    assert invalidate_called, "importlib.invalidate_caches() must be called after a successful install"


def test_install_package_does_not_call_invalidate_caches_on_failure(monkeypatch):
    proc_mock = MagicMock()
    proc_mock.returncode = 1
    proc_mock.stdout = ""
    proc_mock.stderr = "error"

    invalidate_called = []
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: proc_mock)
    monkeypatch.setattr(importlib, "invalidate_caches", lambda: invalidate_called.append(True))

    registry = DependencyRegistry()
    install_package("markitdown", "test reason", dry_run=False, registry=registry)

    assert not invalidate_called, "invalidate_caches should not be called on install failure"


def test_get_installed_version_pymupdf_uses_fitz_module(monkeypatch):
    """get_installed_version('pymupdf') must import 'fitz', not 'pymupdf'."""
    imported_names = []

    def tracking_import(name, *args, **kwargs):
        imported_names.append(name)
        raise ImportError(f"no module named '{name}'")

    monkeypatch.setattr(importlib, "import_module", tracking_import)

    result = get_installed_version("pymupdf")

    assert result is None
    assert "fitz" in imported_names, f"Expected 'fitz' to be imported, got {imported_names}"
    assert "pymupdf" not in imported_names, "Must not import 'pymupdf' directly (use 'fitz')"


def test_get_installed_version_other_packages_use_package_name(monkeypatch):
    imported_names = []

    def tracking_import(name, *args, **kwargs):
        imported_names.append(name)
        raise ImportError(f"no module named '{name}'")

    monkeypatch.setattr(importlib, "import_module", tracking_import)

    get_installed_version("markitdown")
    assert "markitdown" in imported_names
