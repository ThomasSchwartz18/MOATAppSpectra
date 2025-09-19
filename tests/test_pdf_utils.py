import ctypes.util
import importlib
import sys
import types

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


def test_render_html_to_pdf_raises_on_oserror(monkeypatch):
    failing_module = types.ModuleType("weasyprint")

    def _getattr(name: str):  # pragma: no cover - accessed via import
        raise OSError("native dependency load failure")

    failing_module.__getattr__ = _getattr  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "weasyprint", failing_module)

    def failing_fallback(html: str, base_url: str | None = None) -> bytes:
        raise pdf_utils.PdfGenerationError(pdf_utils._FALLBACK_DEPENDENCY_MESSAGE)

    monkeypatch.setattr(
        pdf_utils,
        "_render_html_to_pdf_with_wkhtmltopdf",
        failing_fallback,
    )

    with pytest.raises(pdf_utils.PdfGenerationError) as excinfo:
        pdf_utils.render_html_to_pdf("<p>Hello</p>")

    message = str(excinfo.value)
    assert pdf_utils._REQUIRED_NATIVE_DEPS_MESSAGE in message
    assert pdf_utils._FALLBACK_DEPENDENCY_MESSAGE in message

    monkeypatch.delitem(sys.modules, "weasyprint", raising=False)


def test_render_html_to_pdf_uses_fallback_when_weasyprint_unavailable(monkeypatch):
    def failing_weasyprint(html: str, base_url: str | None = None) -> bytes:
        raise pdf_utils.PdfGenerationError("weasyprint unavailable")

    def successful_fallback(html: str, base_url: str | None = None) -> bytes:
        assert html == "<p>Hello</p>"
        assert base_url == "http://example.com/"
        return b"fake-pdf"

    monkeypatch.setattr(
        pdf_utils, "_render_html_to_pdf_with_weasyprint", failing_weasyprint
    )
    monkeypatch.setattr(
        pdf_utils, "_render_html_to_pdf_with_wkhtmltopdf", successful_fallback
    )

    result = pdf_utils.render_html_to_pdf("<p>Hello</p>", base_url="http://example.com/")

    assert result == b"fake-pdf"


def test_render_html_to_pdf_raises_when_fallback_fails(monkeypatch):
    def failing_weasyprint(html: str, base_url: str | None = None) -> bytes:
        raise pdf_utils.PdfGenerationError("primary failure")

    def failing_fallback(html: str, base_url: str | None = None) -> bytes:
        raise pdf_utils.PdfGenerationError("fallback failure")

    monkeypatch.setattr(
        pdf_utils, "_render_html_to_pdf_with_weasyprint", failing_weasyprint
    )
    monkeypatch.setattr(
        pdf_utils, "_render_html_to_pdf_with_wkhtmltopdf", failing_fallback
    )

    with pytest.raises(pdf_utils.PdfGenerationError) as excinfo:
        pdf_utils.render_html_to_pdf("<p>Hello</p>")

    message = str(excinfo.value)
    assert "primary failure" in message
    assert "fallback failure" in message
