"""Desktop launcher for MOATAppSpectra using pywebview."""

from __future__ import annotations

import socket
import threading
import time
from contextlib import suppress

from dotenv import load_dotenv
from werkzeug.serving import make_server

import webview

from app import create_app


def _find_free_port(host: str = "127.0.0.1") -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return sock.getsockname()[1]


def _wait_for_server(host: str, port: int, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            try:
                sock.connect((host, port))
            except OSError:
                time.sleep(0.1)
            else:
                return
    raise RuntimeError(f"Server did not start within {timeout} seconds")


def run_desktop() -> None:
    load_dotenv()

    app = create_app()
    host = "127.0.0.1"
    port = _find_free_port(host)

    server = make_server(host, port, app)

    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    try:
        _wait_for_server(host, port)
    except Exception:
        server.shutdown()
        with suppress(Exception):
            server.server_close()
        server_thread.join(timeout=2.0)
        raise

    url = f"http://{host}:{port}"
    window = webview.create_window(
        "MOAT App Spectra",
        url,
        fullscreen=True,
    )

    shutdown_event = threading.Event()

    def stop_server() -> None:
        if shutdown_event.is_set():
            return
        shutdown_event.set()
        server.shutdown()
        with suppress(Exception):
            server.server_close()
        if server_thread.is_alive():
            server_thread.join(timeout=2.0)

    window.events.closed += stop_server

    try:
        webview.start()
    finally:
        stop_server()


if __name__ == "__main__":
    run_desktop()
