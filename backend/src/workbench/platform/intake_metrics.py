"""Small process-local Prometheus registry for API and single-purpose worker services."""

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

_values: dict[str, float] = {}
_lock = threading.Lock()


def set_metric(name: str, value: float) -> None:
    with _lock:
        _values[name] = value


def increment(name: str) -> None:
    with _lock:
        _values[name] = _values.get(name, 0) + 1


def render() -> str:
    with _lock:
        return "".join(f"{key} {value}\n" for key, value in sorted(_values.items()))


def start_worker_metrics(port: int = 9100) -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path != "/metrics":
                self.send_error(404)
                return
            body = render().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: Any) -> None:
            return

    # Unpublished Docker-internal endpoint. Local execution binds loopback by default.
    import os

    address = os.environ.get("WB_WORKER_METRICS_BIND", "127.0.0.1")
    server = ThreadingHTTPServer((address, port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
