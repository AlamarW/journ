## Why journ?
journ is a terminal-based journaling app meant to keep you in your terminal. As I've progressed in my development journey, I realized that developers want to stay in their editor/IDE of choice as long as possible. journ is meant to work with your default editor of choice so that you can go from journaling to development all from the ease of the terminal. All while helping you stay accountabile with a daily word goal and streak tracker.

## About the Project
journ started as a project to mimic much of the functionality of the website 750words.com but to make the data local for the users instead of in a cloud. It started to feel weird to me with how much personal stuff I was journaling with on a site with a backend that was not in my control.

Since conception of the project, I've deviated a bit from the clone of 750words.com goal and am dedicating myself to a "fully featured" journaling app in the terminal. The core of journ is that I don't want to take your default text editor from you. People who like to do things in their terminal have their editor of choice (I use neovim btw) and so journ defaults to whatever you have it set up as.

It's helpful to have a word counter in your text editor of choice, but journ will take care of that for you if not (just not as elegantly)

## Installation

journ uses [uv](https://docs.astral.sh/uv/) for packaging. Install it as a standalone tool so
the `journ` command is on your `PATH` and works from any directory, not just the repo:

```sh
git clone https://github.com/AlamarW/journ.git
cd journ
uv tool install .
journ
```

`uv tool install` builds journ into its own isolated environment and links the `journ`
command into `uv`'s tool bin directory (`~/.local/bin` on Linux/macOS,
`%APPDATA%\uv\bin` on Windows). If `journ` isn't found after installing, that directory
probably isn't on your `PATH` yet — run `uv tool update-shell` to fix that, then restart your
shell.

To upgrade after pulling new changes: `uv tool install . --reinstall` from the repo directory.

If you're contributing to journ itself rather than just using it, see
[Development](#development) below instead — that runs it from the repo without a global
install.

`journ` also works on native Windows/PowerShell, not just WSL. On first run, if no `EDITOR`
environment variable is set, Windows users get a one-time picker to choose a text editor
(Notepad, VS Code, Notepad++, Sublime, Vim, or a custom command); the choice is remembered
for next time.

## Choosing your editor

journ opens today's entry in whatever `$EDITOR` (or `$env:EDITOR` on PowerShell) is set to.
If it's unset, journ falls back to `nano` on macOS/Linux, or (on Windows only) offers an
interactive picker the first time and remembers your choice afterward — see above. Run
`journ editor` any time to see what's currently configured, or `journ editor set` to
(re)pick — this works on any platform, not just the automatic Windows prompt.

### journ's built-in editor

Tools like Notepad are fine text editors but have no idea you're journaling — no word count,
no sense of your daily goal. `journ editor set` offers journ's own built-in editor as an
option on every platform (Windows, WSL/Linux, and macOS): a minimal, distraction-free,
full-screen text area with a live word count and goal indicator in the footer.
<kbd>Ctrl+S</kbd> saves and exits, <kbd>Esc</kbd> discards and exits. It's also the only
editor option where your entry never touches disk in plaintext — the external-editor path
below still needs a real temp file for your editor to open, but the built-in editor holds
your entry in memory and encrypts it directly.

To set it yourself:

```sh
# bash / zsh — add to ~/.bashrc or ~/.zshrc
export EDITOR="nvim"
```

```powershell
# PowerShell — add to your $PROFILE to persist it
$env:EDITOR = "code --wait"
```

A few things worth knowing when picking a command:

- **GUI editors need a flag that makes them wait.** journ launches your editor and waits for
  it to exit before reading back what you wrote; editors like VS Code or Sublime normally
  hand control back to the shell immediately, so you need their wait flag: `code --wait` or
  `subl --wait`. Terminal editors (`nvim`, `vim`, `nano`, `emacs -nw`) block naturally and
  don't need this.
- **Multi-word commands work.** `EDITOR="code --wait"` is parsed correctly into the command
  plus its arguments on both POSIX shells and PowerShell.
- **Windows paths with spaces need quotes**, e.g.
  `$env:EDITOR = '"C:\Program Files\Notepad++\notepad++.exe" -multiInst'`.
- **To change a saved Windows picker choice**, either set `$env:EDITOR` (which always takes
  priority), or delete `~/.journ/editor.cfg` to get the picker again next run.

## Usage

Running `journ` with no arguments opens the interactive shell, exactly like before:

```
$ journ
(journ) write
(journ) stats
(journ) streak
(journ) exit
```

Each of those is also available as a scriptable one-shot command, so you don't have to open
the shell just to check something:

| Command                              | What it does                                            |
| ------------------------------------- | -------------------------------------------------------- |
| `journ` / `journ shell`               | Open the interactive `(journ)` shell                     |
| `journ write`                         | Write today's entry in your editor                       |
| `journ stats`                         | Average words-per-minute and total words written         |
| `journ streak`                        | Current streak                                           |
| `journ last`                          | Word count of your most recent entry                     |
| `journ goal` / `journ goal 750`       | Show or set your daily writing goal                       |
| `journ editor` / `journ editor set`   | Show or (re)pick your editor, including the built-in one  |
| `journ passphrase set/change/remove`  | Manage the passphrase that encrypts your entries          |

On first run, journ asks for your daily writing goal and whether you'd like to set a
passphrase.

## Your entries, protected

journ runs entirely on your machine — there's no account system and no server. If you set a
passphrase, it doesn't just gate access to the app: a key derived from it (PBKDF2-HMAC-SHA256
+ Fernet/AES) actually encrypts your entry text before it's written to
`~/.journ/journal.db`. Anyone reading the raw database file without your passphrase sees only
ciphertext. There's no recovery if you forget your passphrase, and metadata that isn't
sensitive on its own (streak, writing goal, entry dates) is stored unencrypted.

The one exposure, if you use an external editor: while it has today's entry open, it's
sitting in a plaintext temp file under `~/.journ/tmp`, deleted as soon as you close the
editor — external editors need a real file on disk to edit. journ's built-in editor
(`journ editor set`) doesn't have this exposure at all; it holds the entry in memory only.

## Development

```sh
uv sync
uv run journ        # run your working copy without a global install
uv run pytest
uv run ruff check .
```
