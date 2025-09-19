"""Utilities for generating PDFs via WeasyPrint."""
from __future__ import annotations

import ctypes.util
import os
import platform
from pathlib import Path
from typing import Iterable


class PdfGenerationError(RuntimeError):
    """Raised when WeasyPrint cannot generate a PDF due to missing libraries."""


_REQUIRED_NATIVE_DEPS_MESSAGE = (
    "Unable to generate PDF exports because WeasyPrint's native dependencies "
    "are missing. Install the Pango, GObject, and Cairo libraries (see the "
    "README for platform-specific instructions) to enable PDF generation."
)


_MAC_LIBRARY_ALIASES: dict[str, tuple[str, ...]] = {
    "libgobject-2.0-0": ("libgobject-2.0.dylib", "libgobject-2.0.0.dylib", "gobject-2.0"),
    "libpango-1.0-0": ("libpango-1.0.dylib", "pango-1.0"),
    "libpangocairo-1.0-0": ("libpangocairo-1.0.dylib", "pangocairo-1.0"),
    "libcairo-2": ("libcairo.2.dylib", "libcairo.dylib", "cairo"),
}

_MAC_LIBRARY_DIR_HINTS: tuple[Path, ...] = (
    Path("/opt/homebrew/lib"),
    Path("/usr/local/lib"),
    Path("/usr/local/opt/pango/lib"),
    Path("/usr/local/opt/cairo/lib"),
    Path("/usr/local/opt/glib/lib"),
)

_PATCHED_FIND_LIBRARY = False
_ORIGINAL_FIND_LIBRARY = ctypes.util.find_library


def _iter_env_library_paths() -> Iterable[Path]:
    """Yield additional library locations from the environment."""

    env_value = os.environ.get("WEASYPRINT_NATIVE_LIB_PATHS", "")
    if not env_value:
        return []

    paths: list[Path] = []
    for raw_path in env_value.split(os.pathsep):
        if not raw_path:
            continue
        candidate = Path(raw_path).expanduser()
        paths.append(candidate)
    return paths


def _mac_library_candidates(name: str) -> list[str]:
    """Return candidate library names for macOS to satisfy Windows aliases."""

    candidates: list[str] = [name]
    if name.startswith("lib"):
        trimmed = name[3:]
        if trimmed:
            candidates.append(trimmed)
    candidates.extend(_MAC_LIBRARY_ALIASES.get(name, ()))

    # Deduplicate while preserving order.
    deduped: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate and candidate not in seen:
            deduped.append(candidate)
            seen.add(candidate)
    return deduped


def _resolve_candidate_path(directory: Path, candidate: str) -> str | None:
    """Resolve a library candidate inside the provided directory."""

    if directory.is_file():
        if directory.name == candidate:
            return str(directory)
        # Allow specifying a file without the lib prefix or suffix.
        stem_match = directory.stem == candidate or directory.stem == candidate.lstrip("lib")
        if stem_match:
            return str(directory)
        return None

    if not directory.is_dir():
        return None

    direct_path = directory / candidate
    if direct_path.exists():
        return str(direct_path)

    # Try common dynamic library suffixes on macOS.
    for suffix in (".dylib", ".so", ".bundle"):
        with_suffix = direct_path.with_suffix(suffix)
        if with_suffix.exists():
            return str(with_suffix)
    return None


def _patched_find_library(name: str) -> str | None:
    """macOS-aware replacement for :func:`ctypes.util.find_library`."""

    if platform.system() != "Darwin":
        return _ORIGINAL_FIND_LIBRARY(name)

    candidates = _mac_library_candidates(name)
    for candidate in candidates:
        located = _ORIGINAL_FIND_LIBRARY(candidate)
        if located:
            return located

    search_paths: list[Path] = list(_iter_env_library_paths())
    search_paths.extend(path for path in _MAC_LIBRARY_DIR_HINTS if path.exists())

    for candidate in candidates:
        for directory in search_paths:
            resolved = _resolve_candidate_path(directory, candidate)
            if resolved:
                return resolved

    return _ORIGINAL_FIND_LIBRARY(name)


def _ensure_native_dependencies_configured() -> None:
    """Ensure platform-specific configuration is applied before imports."""

    global _PATCHED_FIND_LIBRARY
    if _PATCHED_FIND_LIBRARY:
        return

    if platform.system() == "Darwin":
        ctypes.util.find_library = _patched_find_library  # type: ignore[assignment]

    _PATCHED_FIND_LIBRARY = True

    "are missing. Install the Pango, GObject, and Cairo libraries to enable PDF "
    "generation."
)

def render_html_to_pdf(html: str, base_url: str | None = None) -> bytes:
    """Render HTML content to PDF bytes using WeasyPrint.

    Args:
        html: The HTML string to convert into a PDF document.
        base_url: The base URL used by WeasyPrint to resolve relative assets.

    Raises:
        PdfGenerationError: If WeasyPrint or its native dependencies are not
            available on the system.
    """

    try:
        _ensure_native_dependencies_configured()

        from weasyprint import HTML
        from weasyprint.text.fonts import FontConfiguration
    except ImportError as exc:  # pragma: no cover - exercised via tests
        raise PdfGenerationError(_REQUIRED_NATIVE_DEPS_MESSAGE) from exc

    try:
        font_config = FontConfiguration()
        return HTML(string=html, base_url=base_url).write_pdf(
            font_config=font_config
        )
    except OSError as exc:  # pragma: no cover - exercised via tests
        raise PdfGenerationError(_REQUIRED_NATIVE_DEPS_MESSAGE) from exc
