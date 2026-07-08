## Why journ?
journ is a terminal-based journaling app meant to keep you in your terminal. As I've progressed in my development journey, I realized that developers want to stay in their editor/IDE of choice as long as possible. journ is meant to work with your default editor of choice so that you can go from journaling to development all from the ease of the terminal. All while helping you stay accountabile with a daily word goal and streak tracker.

## About the Project
journ started as a project to mimic much of the functionality of the website 750words.com but to make the data local for the users instead of in a cloud. It started to feel weird to me with how much personal stuff I was journaling with on a site with a backend that was not in my control.

Since conception of the project, I've deviated a bit from the clone of 750words.com goal and am dedicating myself to a "fully featured" journaling app in the terminal. The core of journ is that I don't want to take your default text editor from you. People who like to do things in their terminal have their editor of choice (I use neovim btw) and so journ defaults to whatever you have it set up as.

It's helpful to have a word counter in your text editor of choice, but journ will take care of that for you if not (just not as elegantly)

## Installation

journ uses [uv](https://docs.astral.sh/uv/) for packaging.

```sh
git clone https://github.com/AlamarW/journ.git
cd journ
uv sync
uv run journ
```

`journ` also works on native Windows/PowerShell, not just WSL. On first run, if no `EDITOR`
environment variable is set, Windows users get a one-time picker to choose a text editor
(Notepad, VS Code, Notepad++, Sublime, Vim, or a custom command); the choice is remembered
for next time.

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

| Command                            | What it does                                          |
| ----------------------------------- | ------------------------------------------------------ |
| `journ` / `journ shell`             | Open the interactive `(journ)` shell                   |
| `journ write`                       | Write today's entry in your editor                     |
| `journ stats`                       | Average words-per-minute and total words written       |
| `journ streak`                      | Current streak                                         |
| `journ last`                        | Word count of your most recent entry                   |
| `journ goal` / `journ goal 750`     | Show or set your daily writing goal                     |
| `journ passphrase set/change/remove`| Manage the passphrase that encrypts your entries        |

On first run, journ asks for your daily writing goal and whether you'd like to set a
passphrase.

## Your entries, protected

journ runs entirely on your machine — there's no account system and no server. If you set a
passphrase, it doesn't just gate access to the app: a key derived from it (PBKDF2-HMAC-SHA256
+ Fernet/AES) actually encrypts your entry text before it's written to
`~/.journ/journal.db`. Anyone reading the raw database file without your passphrase sees only
ciphertext. There's no recovery if you forget your passphrase, and metadata that isn't
sensitive on its own (streak, writing goal, entry dates) is stored unencrypted.

The one unavoidable exposure: while your editor has today's entry open, it's sitting in a
plaintext temp file under `~/.journ/tmp`, deleted as soon as you close the editor — external
editors need a real file on disk to edit.

## Development

```sh
uv sync
uv run pytest
uv run ruff check .
```
