# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project does

A Windows desktop app that reads the Omega Strikers game log in real time, extracts player awakenings (perks chosen each round), and serves a transparent HTML overlay via a local Flask server. The overlay is added as a Browser Source in OBS for streaming.

## Running the app

```bash
pip install flask watchdog pygetwindow python-dotenv
python main.py
```

Copy `.env.example` to `.env` and configure before running. The app exits immediately if Omega Strikers is not running (unless `TEST_LOG_FLAG=True`).

## Running the test harness

The test runner simulates a full match without the game running:

1. Set in `.env`:
   ```
   TEST_LOG_FLAG=True
   TEST_LOG_FILEPATH=test_game.log
   ```
2. Run:
   ```bash
   python test_runner.py
   ```

This clears `test_game.log`, launches `main.py` in a new console window, waits for the Flask server, then writes log phases every 6 seconds to simulate rounds.

## Building the distributable

```bash
pyinstaller --noconfirm AwakeningOverlayUploader.spec
```

Output goes to `dist/AwakeningOverlayUploader/`. The spec bundles `static/`, `templates/`, `characterImages/`, and `awakeningImages/`.

## Architecture

Data flows in one direction: log file → `observer.py` → `processor.py` → `SharedState` → Flask API → browser overlay.

**`main.py`** — Entry point. Checks if Omega Strikers is open, starts the Flask server thread, starts the log monitor thread, then runs the tkinter GUI event loop.

**`observer.py`** — `LogObserver` wraps watchdog to tail the log file. `LogHandler` holds all in-memory game state (player IGNs, characters, awakenings, teams). On each file modification it reads only new bytes from `file_size` forward. `rescan()` resets all state and re-reads from the last `EMatchPhase::PreGame` marker — used on startup and via the GUI Refresh button.

**`processor.py`** — Stateless log parsing functions called by `LogHandler._process_line()`. Contains the two lookup dicts (`DICT_INTERNAL_TO_EXTERNAL_CHARACTERS`, `DICT_INTERNAL_TO_EXTERNAL_AWAKENINGS`) that map internal game tokens to display names. Key functions:
- `process_log_entry()` — parses a single line, mutates the passed-in state dicts, returns `"CLEAR"`, `True` (consider upload), or `False`/`None`
- `return_true_if_should_upload()` — guards against redundant publishes by comparing candidate table against last published
- `publish_state()` — calls `shared_state.update(players)` to push to the overlay

**`overlay_server.py`** — Flask app with three endpoints: `/` serves `overlay.html`, `/api/state` returns JSON game state, `/img/char/<name>` and `/img/awk/<name>` serve images. Awakening images use fuzzy filename matching (`difflib.SequenceMatcher`) to tolerate name variations. `SharedState` is a thread-safe wrapper with a `game_count` counter used by the browser to detect state changes.

**`gui.py`** — Minimal tkinter window (`StatusWindow`) that shows status messages (polled from a queue), the OBS URL with a copy button, and a Refresh button that calls `LogObserver.rescan()` on a background thread.

**`templates/overlay.html`** — Browser-side overlay. Polls `/api/state` and re-renders when `game_count` changes. Add as OBS Browser Source with "Allow transparency" enabled.

## Key data structures in LogHandler

- `CHARACTERS_LIST` — ordered list of 6 character display names detected in lobby
- `IGN_LIST` — ordered list of 6 player usernames
- `DICT_IGN_TO_AWAKENINGS` — `{ign: [awakening1, awakening2, ...]}` (OrderedDict, grows each round)
- `DICT_IGN_TO_CHARACTER` — `{ign: character_name}`, populated from three log sources in priority order: equipping-trainings lines > Despawn/KO events > Tags exact-match
- `DICT_IGN_TO_TEAM` — `{ign: 1|2}`, from `custom-lobby-roster-v1` WebSocket event; intentionally NOT cleared on game reset

## `.env` variables

| Variable | Default | Purpose |
|---|---|---|
| `OVERLAY_PORT` | `5000` | Flask server port |
| `TEST_LOG_FLAG` | `False` | Use test log instead of live game log |
| `TEST_LOG_FILEPATH` | `test_game.log` | Path used when TEST_LOG_FLAG is True |
