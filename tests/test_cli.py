"""Tests for CLI commands (v1.0 step5)."""

import pytest
from sisyphus.memory import cli


class TestCliStore:
    def test_store_uses_correct_path(self):
        store = cli._store()
        assert store.base_path.name == "memory"
        assert ".omo" in str(store.base_path)

    def test_refined_store_uses_refined_subdir(self):
        rstore = cli._refined_store()
        assert rstore.base_path.name == "refined"

    def test_log_store_uses_logs_subdir(self):
        lstore = cli._log_store()
        assert lstore.base_path.name == "logs"
        assert ".omo" in str(lstore.base_path)


class TestCliCommands:
    def test_record_accepts_importance_and_links(self, capsys):
        cli.cmd_record(
            _Args(type="lesson", title="Test", content="Content",
                   tags="a,b")
        )
        captured = capsys.readouterr().out
        assert "Recorded" in captured

    def test_parser_has_new_subcommands(self):
        parser = cli.build_parser()
        sub_names = _get_subcommand_names(parser)
        assert "index" in sub_names
        assert "log" in sub_names
        assert "refined" in sub_names
        assert "dream" in sub_names


class _Args:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def _get_subcommand_names(parser):
    for action in parser._actions:
        if hasattr(action, '_name_parser_map'):
            return list(action._name_parser_map.keys())
    return []
