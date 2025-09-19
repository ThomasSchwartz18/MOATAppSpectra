import ctypes.util
import importlib

import pytest

from app.main import pdf_utils


@pytest.fixture
def reset_find_library():
    """Reset ctypes.util.find_library after tests that monkeypatch it."""

    original = ctypes.util.find_library
    yield
    ctypes.util.find_library = original
    pdf_utils._PATCHED_FIND_LIBRARY = False


def test_macos_env_hint_used_for_gobject(monkeypatch, tmp_path, reset_find_library):
    # Reload the module to ensure the original finder is captured for the patch.
    importlib.reload(pdf_utils)

    libs_dir = tmp_path / "libs"
    libs_dir.mkdir()
    lib_path = libs_dir / "libgobject-2.0.dylib"
    lib_path.write_text("")

    monkeypatch.setenv("WEASYPRINT_NATIVE_LIB_PATHS", str(libs_dir))
    monkeypatch.setattr(pdf_utils, "_ORIGINAL_FIND_LIBRARY", lambda name: None)
    monkeypatch.setattr(pdf_utils.platform, "system", lambda: "Darwin")

    pdf_utils._PATCHED_FIND_LIBRARY = False
    pdf_utils._ensure_native_dependencies_configured()

    resolved = ctypes.util.find_library("libgobject-2.0-0")
    assert resolved == str(lib_path)


def test_nonexistent_hint_falls_back(monkeypatch, reset_find_library):
    importlib.reload(pdf_utils)

    calls: list[str] = []

    def fake_original(name: str) -> str | None:
        calls.append(name)
        return None

    monkeypatch.setattr(pdf_utils, "_ORIGINAL_FIND_LIBRARY", fake_original)
    monkeypatch.setattr(pdf_utils.platform, "system", lambda: "Darwin")

    pdf_utils._PATCHED_FIND_LIBRARY = False
    pdf_utils._ensure_native_dependencies_configured()

    # Should return None when neither aliases nor hints can resolve the library.
    result = ctypes.util.find_library("libunknown-1.0-0")
    assert result is None
    # Ensure the alias candidates were attempted.
    assert "libunknown-1.0-0" in calls
