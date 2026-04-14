#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import socket
import sys
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve HappyTrace locally.")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind. Default: 127.0.0.1")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind. Default: 8000")
    parser.add_argument("--open", action="store_true", help="Open the viewer in your default browser.")
    return parser.parse_args()


def resolve_urls(host: str, port: int) -> list[str]:
    urls = [f"http://{host}:{port}/happytrace.html"]
    if host == "0.0.0.0":
        urls.append(f"http://localhost:{port}/happytrace.html")
        try:
            local_ip = socket.gethostbyname(socket.gethostname())
        except OSError:
            local_ip = ""
        if local_ip and not local_ip.startswith("127."):
            urls.append(f"http://{local_ip}:{port}/happytrace.html")
    return urls


def main() -> None:
    args = parse_args()
    repo_root = Path(__file__).resolve().parent.parent
    handler = partial(SimpleHTTPRequestHandler, directory=os.fspath(repo_root))
    server = ThreadingHTTPServer((args.host, args.port), handler)

    urls = resolve_urls(args.host, args.port)
    print(f"Serving HappyTrace from: {repo_root}")
    for url in urls:
        print(f"Open: {url}")
    print("Press Ctrl+C to stop.")

    if args.open:
        webbrowser.open(urls[0])

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server.", file=sys.stderr)
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
