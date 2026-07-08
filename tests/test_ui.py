import re

from journ import ui

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


def test_welcome_banner_box_columns_are_aligned(capsys):
    ui.print_welcome()
    output = _ANSI_RE.sub("", capsys.readouterr().out)
    lines = output.splitlines()

    box_lines = [line for line in lines if "+" in line or "|" in line]
    assert len(box_lines) == 4
    box_starts = [line.index("+") if "+" in line else line.index("|") for line in box_lines]
    assert len(set(box_starts)) == 1, f"banner box columns are misaligned: {box_lines!r}"


def test_stats_table_has_no_ansi_when_non_tty(capsys):
    ui.print_stats_table(avg_wpm=42.0, total_words=100, entry_count=3)
    output = capsys.readouterr().out
    assert "\x1b[" not in output
    assert "Total words written" in output
