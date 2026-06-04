from typer.testing import CliRunner

from crawler.cli import app

runner = CliRunner()


def test_build_masters_command_registered():
    result = runner.invoke(app, ["build-masters", "--help"])
    assert result.exit_code == 0
    assert "masters.json" in result.output or "masters" in result.output
