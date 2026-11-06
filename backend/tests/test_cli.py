from __future__ import annotations

from app.cli import main


def test_eval_gate_passes_for_the_good_mock_model(capsys):
    code = main(["--db", "sqlite://", "eval", "--version", "1", "--min-score", "0.9"])
    out = capsys.readouterr().out
    assert code == 0
    assert "Gate passed" in out
    assert "mean score" in out


def test_eval_gate_fails_for_the_sloppy_mock_model(capsys):
    code = main(["--db", "sqlite://", "eval", "--version", "2", "--min-score", "0.9"])
    out = capsys.readouterr().out
    assert code == 1
    assert "Gate failed" in out
    assert "FAILED" in out


def test_eval_with_model_override_creates_a_version(capsys):
    code = main(
        [
            "--db",
            "sqlite://",
            "eval",
            "--version",
            "1",
            "--model",
            "mock-sloppy",
            "--min-score",
            "0.9",
        ]
    )
    assert code == 1
    assert "winloss-rag v3" in capsys.readouterr().out


def test_unknown_agent_and_dataset_are_reported(capsys):
    assert main(["--db", "sqlite://", "eval", "--agent", "nope"]) == 2
    assert main(["--db", "sqlite://", "eval", "--dataset", "nope"]) == 2
    assert main(["--db", "sqlite://", "eval", "--version", "9"]) == 2
    assert "Unknown agent" in capsys.readouterr().err


def test_seed_command(capsys):
    assert main(["--db", "sqlite://", "seed"]) == 0
    assert "Documents: 16" in capsys.readouterr().out
