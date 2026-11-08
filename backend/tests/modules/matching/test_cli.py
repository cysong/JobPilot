"""CLI wiring checks."""
from __future__ import annotations

import subprocess
import sys

import pytest


def test_cli_registers_all_models_so_mappers_configure():
    # Run in a fresh interpreter: other tests may already have imported app.models.
    code = (
        "import app.modules.matching.cli\n"
        "from sqlalchemy.orm import configure_mappers\n"
        "configure_mappers()\n"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr[-2000:]


@pytest.mark.parametrize("argv", [
    ["families", "classify-titles", "--all"],
    ["families", "init", "--days", "7"],
    ["resumes", "suggest", "--user", "1", "--apply"],
    ["resumes", "set", "res_1", "qa_test"],
    ["dataset", "create", "--user", "1"],
    ["run", "--dataset", "main@v1", "--judged-limit", "200", "--repeat", "2", "--repeat-sample", "100"],
    ["report", "mer_1"],
    ["compare", "mer_1", "mer_2"],
    ["labels", "export", "--run", "mer_1"],
    ["labels", "import", "--file", "x.csv", "--labeled-by", "1"],
])
def test_parser_accepts_documented_commands(argv):
    from app.modules.matching.cli import build_parser

    args = build_parser().parse_args(argv)
    assert callable(args.func)
    if hasattr(args, "yes"):
        assert args.yes is False  # LLM commands default to dry run
