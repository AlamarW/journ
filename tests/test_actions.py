from journ import actions, config


def test_builtin_editor_never_touches_tmp_dir_and_skips_redundant_goal_line(
    db, tmp_path, monkeypatch, capsys
):
    db.create_profile(writing_goal=5)
    monkeypatch.setattr(config, "journ_tmp_dir", tmp_path / "tmp")
    monkeypatch.setattr(actions.config, "get_editor", lambda: config.BUILTIN_EDITOR)
    monkeypatch.setattr(
        actions, "run_builtin_editor", lambda initial_text, writing_goal: "written via builtin"
    )

    actions.write_today_entry(db)

    assert not (tmp_path / "tmp").exists() or list((tmp_path / "tmp").glob("*")) == []

    entry = db.latest_entry()
    assert entry is not None
    assert entry.content.decode("utf-8") == "written via builtin"

    output = capsys.readouterr().out
    assert "over your goal" not in output
    assert "under your goal" not in output
    assert "Streak" in output or "streak" in output


def test_external_editor_still_prints_goal_line(db, tmp_path, monkeypatch, capsys):
    db.create_profile(writing_goal=5)
    stub = tmp_path / "stub.py"
    stub.write_text(
        "import sys\n"
        "with open(sys.argv[1], 'a', encoding='utf-8') as f:\n"
        "    f.write('some words written externally today')\n"
    )
    monkeypatch.setattr(config, "journ_tmp_dir", tmp_path / "tmp")
    monkeypatch.setattr(actions.config, "get_editor", lambda: f"python3 {stub}")

    actions.write_today_entry(db)

    output = capsys.readouterr().out
    assert "your goal" in output
