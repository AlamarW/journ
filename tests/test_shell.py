from journ.shell import _HELP_GROUPS, JournalingShell


def test_help_groups_exclude_alias_noise():
    # journ/EOF are backward-compat aliases for write/exit, not separate commands --
    # checking the source of truth is more robust than string-matching printed output
    # (whose title, "journ commands", would otherwise make a substring check misfire).
    listed_commands = {name for _, names in _HELP_GROUPS for name in names}
    assert "journ" not in listed_commands
    assert "EOF" not in listed_commands


def test_help_lists_grouped_commands(db, capsys):
    db.create_profile(writing_goal=750)
    shell = JournalingShell(db)

    shell.do_help("")

    output = capsys.readouterr().out
    for section in ("Write", "Analytics", "Configuration", "Shell"):
        assert section in output
    for command in ("write", "calendar", "search", "editor", "passphrase", "exit"):
        assert command in output


def test_help_with_argument_shows_single_command_detail(db, capsys):
    db.create_profile(writing_goal=750)
    shell = JournalingShell(db)

    shell.do_help("write")

    output = capsys.readouterr().out
    assert "Write today's journal entry" in output
    # Shouldn't fall through to the full grouped table for a specific command.
    assert "Analytics" not in output
