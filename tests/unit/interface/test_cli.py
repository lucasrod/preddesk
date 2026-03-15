"""Unit tests for the CLI interface.

The CLI provides basic commands for interacting with PredDesk
from the terminal: health check, listing markets, and starting the server.
"""

from unittest.mock import patch

from preddesk.interface.cli import build_parser, cmd_health, cmd_version, main


class TestCLIParser:
    def test_version_command(self):
        parser = build_parser()
        args = parser.parse_args(["version"])
        assert args.command == "version"

    def test_health_command(self):
        parser = build_parser()
        args = parser.parse_args(["health"])
        assert args.command == "health"

    def test_serve_command_defaults(self):
        parser = build_parser()
        args = parser.parse_args(["serve"])
        assert args.command == "serve"
        assert args.host == "127.0.0.1"
        assert args.port == 8000

    def test_serve_command_custom_port(self):
        parser = build_parser()
        args = parser.parse_args(["serve", "--port", "9000", "--host", "0.0.0.0"])
        assert args.port == 9000
        assert args.host == "0.0.0.0"


class TestCmdVersion:
    def test_prints_version(self, capsys):
        cmd_version()
        captured = capsys.readouterr()
        assert "PredDesk" in captured.out
        assert "0.1.0" in captured.out


class TestCmdHealth:
    def test_prints_ok(self, capsys):
        cmd_health()
        captured = capsys.readouterr()
        assert "ok" in captured.out.lower()


class TestMainDispatch:
    """Test the main() entry point dispatches commands correctly."""

    def test_main_version(self, capsys):
        with patch("sys.argv", ["preddesk", "version"]):
            main()
        captured = capsys.readouterr()
        assert "PredDesk" in captured.out

    def test_main_health(self, capsys):
        with patch("sys.argv", ["preddesk", "health"]):
            main()
        captured = capsys.readouterr()
        assert "ok" in captured.out.lower()

    def test_main_no_command_prints_help(self, capsys):
        with patch("sys.argv", ["preddesk"]):
            main()
        captured = capsys.readouterr()
        assert "usage" in captured.out.lower() or "preddesk" in captured.out.lower()

    def test_main_serve_calls_uvicorn(self):
        with (
            patch("sys.argv", ["preddesk", "serve", "--port", "9999"]),
            patch("uvicorn.run") as mock_run,
        ):
            main()
        mock_run.assert_called_once_with(
            "preddesk.interface.api:create_app",
            host="127.0.0.1",
            port=9999,
            factory=True,
        )

    def test_main_serve_missing_uvicorn(self, capsys):
        with (
            patch("sys.argv", ["preddesk", "serve"]),
            patch.dict("sys.modules", {"uvicorn": None}),
        ):
            main()
        captured = capsys.readouterr()
        assert "uvicorn is required" in captured.out
