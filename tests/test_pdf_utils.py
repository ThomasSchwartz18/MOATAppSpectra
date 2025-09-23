import ctypes.util
import importlib.util
import sys
import types
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).resolve().parents[1] / "app" / "main" / "pdf_utils.py"


def _load_pdf_utils() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("pdf_utils", _MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _reload_pdf_utils() -> None:
    globals()["pdf_utils"] = _load_pdf_utils()


pdf_utils = _load_pdf_utils()


@pytest.fixture
def reset_find_library():
    """Reset ctypes.util.find_library after tests that monkeypatch it."""

    original = ctypes.util.find_library
    yield
    ctypes.util.find_library = original
    pdf_utils._PATCHED_FIND_LIBRARY = False


def test_macos_env_hint_used_for_gobject(monkeypatch, tmp_path, reset_find_library):
    # Reload the module to ensure the original finder is captured for the patch.
    _reload_pdf_utils()

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
    _reload_pdf_utils()

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

    def failing_chromium(html: str, base_url: str | None = None) -> bytes:
        raise pdf_utils.PdfGenerationError(pdf_utils._CHROMIUM_DEPENDENCY_MESSAGE)

    def failing_fallback(html: str, base_url: str | None = None) -> bytes:
        raise pdf_utils.PdfGenerationError(pdf_utils._FALLBACK_DEPENDENCY_MESSAGE)

    monkeypatch.setattr(
        pdf_utils,
        "_render_html_to_pdf_with_wkhtmltopdf",
        failing_fallback,
    )
    monkeypatch.setattr(
        pdf_utils,
        "_render_html_to_pdf_with_chromium",
        failing_chromium,
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

    def successful_chromium(html: str, base_url: str | None = None) -> bytes:
        assert html == "<p>Hello</p>"
        assert base_url == "http://example.com/"
        return b"fake-pdf"

    def failing_wkhtmltopdf(html: str, base_url: str | None = None) -> bytes:
        raise pdf_utils.PdfGenerationError("wkhtmltopdf should not be used")

    monkeypatch.setattr(
        pdf_utils, "_render_html_to_pdf_with_weasyprint", failing_weasyprint
    )
    monkeypatch.setattr(
        pdf_utils, "_render_html_to_pdf_with_chromium", successful_chromium
    )
    monkeypatch.setattr(
        pdf_utils,
        "_render_html_to_pdf_with_wkhtmltopdf",
        failing_wkhtmltopdf,
    )

    result = pdf_utils.render_html_to_pdf("<p>Hello</p>", base_url="http://example.com/")

    assert result == b"fake-pdf"


def test_render_html_to_pdf_raises_when_fallback_fails(monkeypatch):
    def failing_weasyprint(html: str, base_url: str | None = None) -> bytes:
        raise pdf_utils.PdfGenerationError("primary failure")

    def failing_chromium(html: str, base_url: str | None = None) -> bytes:
        raise pdf_utils.PdfGenerationError("chromium failure")

    def failing_fallback(html: str, base_url: str | None = None) -> bytes:
        raise pdf_utils.PdfGenerationError("fallback failure")

    monkeypatch.setattr(
        pdf_utils, "_render_html_to_pdf_with_weasyprint", failing_weasyprint
    )
    monkeypatch.setattr(
        pdf_utils, "_render_html_to_pdf_with_chromium", failing_chromium
    )
    monkeypatch.setattr(
        pdf_utils, "_render_html_to_pdf_with_wkhtmltopdf", failing_fallback
    )

    with pytest.raises(pdf_utils.PdfGenerationError) as excinfo:
        pdf_utils.render_html_to_pdf("<p>Hello</p>")

    message = str(excinfo.value)
    assert "primary failure" in message
    assert "fallback failure" in message


def test_render_html_to_pdf_raises_on_macos(monkeypatch):
    monkeypatch.setattr(pdf_utils.platform, "system", lambda: "Darwin")

    with pytest.raises(pdf_utils.PdfGenerationError) as excinfo:
        pdf_utils.render_html_to_pdf("<p>Hello</p>")

    message = str(excinfo.value)
    assert message == pdf_utils._MAC_UNSUPPORTED_MESSAGE


class FakePage:
    def __init__(self) -> None:
        self.set_content_calls: list[dict[str, object]] = []
        self.pdf_kwargs: dict[str, object] | None = None

    def set_content(
        self,
        html: str,
        *,
        wait_until: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.set_content_calls.append(
            {"html": html, "wait_until": wait_until, "base_url": base_url}
        )

    def pdf(self, **kwargs):
        self.pdf_kwargs = kwargs
        return b"fake-pdf"


class FakeBrowser:
    def __init__(self, page: FakePage) -> None:
        self.page = page
        self.closed = False

    def new_page(self) -> FakePage:
        return self.page

    def close(self) -> None:
        self.closed = True


class FakeChromium:
    def __init__(self, browser: FakeBrowser) -> None:
        self.browser = browser
        self.launch_calls: list[dict[str, object]] = []

    def launch(self, **kwargs) -> FakeBrowser:
        self.launch_calls.append(kwargs)
        return self.browser


class FakePlaywrightContext:
    def __init__(self, chromium: FakeChromium) -> None:
        self.chromium = chromium

    def __enter__(self) -> "FakePlaywrightContext":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # pragma: no cover - passthrough
        return None


def test_render_html_to_pdf_with_chromium_uses_css_page_size(monkeypatch):
    fake_page = FakePage()
    fake_browser = FakeBrowser(fake_page)
    fake_chromium = FakeChromium(fake_browser)
    context = FakePlaywrightContext(fake_chromium)

    def fake_sync_playwright():
        return context

    sync_api_module = types.ModuleType("playwright.sync_api")
    sync_api_module.sync_playwright = fake_sync_playwright
    playwright_module = types.ModuleType("playwright")
    playwright_module.sync_api = sync_api_module

    monkeypatch.setitem(sys.modules, "playwright", playwright_module)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", sync_api_module)

    result = pdf_utils._render_html_to_pdf_with_chromium(
        "<p>Hello</p>", base_url="http://example.com/"
    )

    assert result == b"fake-pdf"
    assert fake_page.pdf_kwargs is not None
    assert fake_page.pdf_kwargs.get("prefer_css_page_size") is True
    assert fake_page.pdf_kwargs.get("print_background") is True
    assert fake_page.pdf_kwargs.get("margin") == {
        "top": "0",
        "right": "0",
        "bottom": "0",
        "left": "0",
    }
