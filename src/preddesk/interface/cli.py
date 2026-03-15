"""CLI interface for PredDesk.

Provides basic commands: version, health check, and starting the API server.
"""

from __future__ import annotations

import argparse

VERSION = "0.1.0"


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the CLI."""
    parser = argparse.ArgumentParser(
        prog="preddesk",
        description="PredDesk — Prediction Markets Research Workbench",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("version", help="Show version")
    sub.add_parser("health", help="Health check")

    serve_parser = sub.add_parser("serve", help="Start the API server")
    serve_parser.add_argument("--host", default="127.0.0.1", help="Bind host")
    serve_parser.add_argument("--port", type=int, default=8000, help="Bind port")

    return parser


def cmd_version() -> None:
    """Print the version string."""
    print(f"PredDesk v{VERSION}")


def cmd_health() -> None:
    """Print a simple health status."""
    print("Status: OK")


def main() -> None:
    """Entry point for the CLI."""
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "version":
        cmd_version()
    elif args.command == "health":
        cmd_health()
    elif args.command == "serve":
        try:
            import uvicorn
        except ImportError:
            print("uvicorn is required to serve. Install it with: uv add uvicorn")
            return
        uvicorn.run(
            "preddesk.interface.api:create_app",
            host=args.host,
            port=args.port,
            factory=True,
        )
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
