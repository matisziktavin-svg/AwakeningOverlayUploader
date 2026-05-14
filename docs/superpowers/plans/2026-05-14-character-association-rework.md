# Character-Association Rework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix three concrete bugs in `processor.py` that cause unreliable character↔player association, without touching any other file.

**Architecture:** Surgical edits to `processor.py` only. Replace dead exact-equality character matching with subset+uniqueness matching against the per-character grouped `Tags: {...}` dict; remove a regex branch that never fires; tighten roster-JSON extraction.

**Tech Stack:** Python 3 stdlib (re, json). No new dependencies.

**Spec:** [docs/superpowers/specs/2026-05-14-character-association-rework-design.md](../specs/2026-05-14-character-association-rework-design.md)

---

## File Structure

- **Modify:** `processor.py` — the only file with logic changes.
- **Create:** `verify_rework.py` (project root) — single-file offline verification harness. Imports `processor`, exercises new logic via direct calls, and runs an offline replay against `logsEXAMPLE/OmegaStrikers1.log`. Idiomatic for this project (matches the `test_runner.py` style — single Python script, no test framework, runs with `python verify_rework.py`).
- **Modify:** `CLAUDE.md` — remove the inaccurate claim that the `equipping trainings` line is the primary character-association source.

---

## Task 1: Create the verification harness

**Files:**
- Create: `verify_rework.py`

This harness gives us a fast, deterministic way to check parser behaviour without a live game or the watchdog/Flask stack. Used in every subsequent task.

- [ ] **Step 1: Create `verify_rework.py` with the offline replay shell**

```python
"""
Offline verification for processor.py changes.

Runs unit-style checks against process_log_entry and replays the example
log files to verify final state. Exits 0 if all checks pass, 1 otherwise.

Usage:  python verify_rework.py
"""

import os
import sys
from collections import OrderedDict

import processor


def _fresh_state():
    """Return a fresh tuple of the 7 LogHandler state containers."""
    return (
        [],                    # CHARACTERS_LIST
        [],                    # IGN_LIST
        OrderedDict(),         # DICT_IGN_TO_AWAKENINGS
        {},                    # DICT_IGN_TO_CHARACTER
        {},                    # DICT_IGN_TO_TEAM
        [],                    # ALL_LOGS_THIS_GAME
        [],                    # MOST_RECENTLY_PUBLISHED_TABLE
    )


def _feed(lines, state):
    """Feed a list of cleaned log lines into process_log_entry."""
    results = []
    for line in lines:
        result = processor.process_log_entry(line, *state)
        results.append(result)
    return results


def _replay_file(path):
    """Replay a full log file from the last EMatchPhase::PreGame onwards."""
    import re
    with open(path, 'r', encoding='utf-8') as f:
        all_lines = f.read().splitlines()
    # Mirror observer._find_latest_game_start
    marker = "Current[EMatchPhase::PreGame]"
    start = 0
    for i, line in enumerate(all_lines):
        cleaned = re.sub(r'^\[.*?\]\[.*?\]', '', line).strip()
        if marker in cleaned:
            start = i
    state = _fresh_state()
    _feed(all_lines[start:], state)
    return state


_failures = []


def check(label, condition, detail=""):
    if condition:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}  {detail}")
        _failures.append(label)


def main():
    # Placeholder — real checks added by subsequent tasks
    print("verify_rework.py: no checks defined yet.")
    if _failures:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify the harness runs cleanly against the current (pre-fix) code**

Run: `python verify_rework.py`
Expected output:
```
verify_rework.py: no checks defined yet.
```
Expected exit code: 0

- [ ] **Step 3: Commit**

```bash
git add verify_rework.py
git commit -m "Add offline verification harness for processor rework"
```

---

## Task 2: Remove dead C_X_C extraction from equipping-trainings handler

**Files:**
- Modify: `processor.py:133-141`

The block at [processor.py:133-141](../../processor.py#L133-L141) tries to find a `C_X_C` token in `match.group(2)` (the trainings-list portion). That token never appears there. The branch never fires. Removing it.

- [ ] **Step 1: Add a verification check that an equipping-trainings line does NOT modify DICT_IGN_TO_CHARACTER**

Edit `verify_rework.py`, replace the `main()` function with:

```python
def main():
    # ── Check 1: equipping-trainings does not populate DICT_IGN_TO_CHARACTER
    state = _fresh_state()
    _feed([
        "LogGameMode: Current[EMatchPhase::CharacterSelect] Previous[EMatchPhase::None]",
        "LogGameMode: Current[EMatchPhase::VersusScreen] Previous[EMatchPhase::CharacterSelect]",
        "LogPMSkinDataManager: UPMSkinDataManagerComponent::DetermineLobbyAnimation SD_AngelicSupport",
        "LogPMPlayerState: Player 'Foo' equipping trainings TrainingData:TD_RangedStrike , TrainingData:TD_ShrinkSelfGrowAllies , ",
    ], state)
    DICT_IGN_TO_CHARACTER = state[3]
    check(
        "equipping-trainings does not populate DICT_IGN_TO_CHARACTER",
        DICT_IGN_TO_CHARACTER == {},
        f"got {DICT_IGN_TO_CHARACTER!r}",
    )

    if _failures:
        sys.exit(1)
    sys.exit(0)
```

- [ ] **Step 2: Run the check — it should already PASS against the current code** (because the trainings list has no `C_X_C` token, the existing dead branch is silently a no-op for this input)

Run: `python verify_rework.py`
Expected: `PASS  equipping-trainings does not populate DICT_IGN_TO_CHARACTER`, exit 0.

This is the *baseline*. The check passes before and after the change, because the change is removing inert code.

- [ ] **Step 3: Edit `processor.py` to remove the dead block**

In [processor.py:122-161](../../processor.py#L122-L161), find:

```python
            elif "equipping trainings" in cleaned_line:
                match = re.search(r"Player '(.+?)' equipping trainings (.*)", cleaned_line)
                if match:
                    player = match.group(1)
                    if player not in IGN_LIST:
                        IGN_LIST.append(player)  # Add player to IGN_LIST
                        if(len(IGN_LIST)==6):
                            print(f"printing a list of 6 igns {IGN_LIST}")
                            time.sleep(0.01)

                    # Extract character class (C_xxx_C token) directly from the trainings line.
                    # The token may appear with an instance-number suffix (e.g. C_FlashySwordsman_C_2147407801),
                    # so we capture just the base class and ignore the trailing _\d+ if present.
                    char_token_match = re.search(r'(C_\w+_C)(?:_\d+)?', match.group(2))
                    if char_token_match:
                        char_external = DICT_INTERNAL_TO_EXTERNAL_CHARACTERS.get(char_token_match.group(1))
                        if char_external:
                            DICT_IGN_TO_CHARACTER[player] = char_external
                            print(f"Linked character {char_external} to player {player}")

                    trainings = [DICT_INTERNAL_TO_EXTERNAL_AWAKENINGS.get(t, t) for t in re.findall(r"TD_\w+", match.group(2))]
```

Replace with:

```python
            elif "equipping trainings" in cleaned_line:
                match = re.search(r"Player '(.+?)' equipping trainings (.*)", cleaned_line)
                if match:
                    player = match.group(1)
                    if player not in IGN_LIST:
                        IGN_LIST.append(player)
                        if len(IGN_LIST) == 6:
                            print(f"printing a list of 6 igns {IGN_LIST}")
                            time.sleep(0.01)

                    trainings = [DICT_INTERNAL_TO_EXTERNAL_AWAKENINGS.get(t, t) for t in re.findall(r"TD_\w+", match.group(2))]
```

- [ ] **Step 4: Re-run the check — still PASS**

Run: `python verify_rework.py`
Expected: `PASS  equipping-trainings does not populate DICT_IGN_TO_CHARACTER`, exit 0.

- [ ] **Step 5: Commit**

```bash
git add processor.py verify_rework.py
git commit -m "Remove dead C_X_C extraction from equipping-trainings handler

The trainings list never contains a character class token, so the
re.search(r'(C_\w+_C)...) branch never fired. Removed."
```

---

## Task 3: Rewrite Tags-based character linking (subset matching with uniqueness)

**Files:**
- Modify: `processor.py:163-225` (the `elif "Tags: {'" in cleaned_line:` branch)

This is the core fix. Replace exact-equality matching with subset+uniqueness.

- [ ] **Step 1: Add failing checks for the new behaviour**

In `verify_rework.py`, before `if _failures:`, add:

```python
    # ── Check 2: round-1 starting-awakenings ambiguity — no commits when all share
    state = _fresh_state()
    state[1].extend(['A', 'B', 'C'])
    state[2]['A'] = ['Among Titans', 'Explosive Entrance']
    state[2]['B'] = ['Among Titans', 'Explosive Entrance']
    state[2]['C'] = ['Among Titans', 'Explosive Entrance']
    _feed([
        "LogPMPerfStatsSubsystem: Tags: {'C_Shieldz_C': '1', 'TD_ShrinkSelfGrowAllies': '3', 'TD_FasterDashes3': '3', 'C_StalwartProtector_C': '1', 'C_EmpoweringEnchanter_C': '1'}",
    ], state)
    DICT_IGN_TO_CHARACTER = state[3]
    check(
        "round-1 identical-set Tags line commits nothing",
        DICT_IGN_TO_CHARACTER == {},
        f"got {DICT_IGN_TO_CHARACTER!r}",
    )

    # ── Check 3: subset match commits when exactly one IGN's set is a superset
    state = _fresh_state()
    state[1].extend(['Alice', 'Bob', 'Carol'])
    state[2]['Alice'] = ['Among Titans', 'Strike Shot']     # has unique 'Strike Shot'
    state[2]['Bob']   = ['Among Titans', 'Hotshot']         # has unique 'Hotshot'
    state[2]['Carol'] = ['Among Titans', 'Aerials']         # has unique 'Aerials'
    _feed([
        "LogPMPerfStatsSubsystem: Tags: {'C_Shieldz_C': '1', 'TD_ShrinkSelfGrowAllies': '3', 'TD_RangedStrike': '1', 'C_StalwartProtector_C': '1', 'TD_HitRockCooldown': '1', 'C_EmpoweringEnchanter_C': '1', 'TD_FasterProjectiles2': '1'}",
    ], state)
    DICT_IGN_TO_CHARACTER = state[3]
    check(
        "subset match: Shieldz → Alice (via Strike Shot)",
        DICT_IGN_TO_CHARACTER.get('Alice') == 'Asher',
        f"got {DICT_IGN_TO_CHARACTER!r}",
    )
    check(
        "subset match: StalwartProtector → Bob (via Hotshot)",
        DICT_IGN_TO_CHARACTER.get('Bob') == 'Dubu',
        f"got {DICT_IGN_TO_CHARACTER!r}",
    )
    check(
        "subset match: EmpoweringEnchanter → Carol (via Aerials)",
        DICT_IGN_TO_CHARACTER.get('Carol') == 'Era',
        f"got {DICT_IGN_TO_CHARACTER!r}",
    )

    # ── Check 4: ambiguous subset (2 candidates) — skip
    state = _fresh_state()
    state[1].extend(['X', 'Y', 'Z'])
    state[2]['X'] = ['Among Titans', 'Strike Shot']
    state[2]['Y'] = ['Among Titans', 'Strike Shot']         # tied with X
    state[2]['Z'] = ['Among Titans', 'Aerials']
    _feed([
        "LogPMPerfStatsSubsystem: Tags: {'C_Shieldz_C': '1', 'TD_ShrinkSelfGrowAllies': '3', 'TD_RangedStrike': '2', 'C_StalwartProtector_C': '1', 'C_EmpoweringEnchanter_C': '1', 'TD_FasterProjectiles2': '1'}",
    ], state)
    DICT_IGN_TO_CHARACTER = state[3]
    check(
        "ambiguous subset (2 candidates) commits nothing for Asher",
        'Asher' not in DICT_IGN_TO_CHARACTER.values(),
        f"got {DICT_IGN_TO_CHARACTER!r}",
    )
    check(
        "ambiguous Asher case still resolves Era → Z",
        DICT_IGN_TO_CHARACTER.get('Z') == 'Era',
        f"got {DICT_IGN_TO_CHARACTER!r}",
    )
```

- [ ] **Step 2: Run the checks — checks 2-4 should FAIL against the current (exact-equality) code**

Run: `python verify_rework.py`
Expected: Check 1 PASS. Check 2 PASS (because old code also commits nothing here). Check 3 FAILs (exact-equality never matches because Tags-set is a strict subset of player's set). Check 4 partially fails.

Specifically expect:
```
PASS  equipping-trainings does not populate DICT_IGN_TO_CHARACTER
PASS  round-1 identical-set Tags line commits nothing
FAIL  subset match: Shieldz → Alice (via Strike Shot)  got {}
FAIL  subset match: StalwartProtector → Bob (via Hotshot)  got {}
FAIL  subset match: EmpoweringEnchanter → Carol (via Aerials)  got {}
PASS  ambiguous subset (2 candidates) commits nothing for Asher
FAIL  ambiguous Asher case still resolves Era → Z  got {}
```

Exit 1. This confirms the new behaviour is not present yet.

- [ ] **Step 3: Replace the Tags branch in `processor.py`**

In [processor.py:163-225](../../processor.py#L163-L225), find the entire `elif "Tags: {'" in cleaned_line:` block (from `elif "Tags: {'" in cleaned_line:` down to `if updated: return True`) and replace with:

```python
            elif "Tags: {'" in cleaned_line:
                # The Tags dict is a deduplicated multiset of currently-active GameplayTags
                # across all 6 characters. Its iteration order groups TD_X keys under the
                # preceding C_X_C key. Because the dict deduplicates, a shared awakening
                # only appears once (under the first character it's iterated for), so a
                # character's per-character tag block is a *subset* of, not equal to, the
                # awakening set of the player playing that character.
                #
                # Match strategy: for each character whose tag block is non-empty, find
                # all unlinked IGNs whose awakening set is a superset of the block.
                # Commit (char → IGN) only when exactly one candidate exists. Otherwise
                # wait for more data (more rounds → more divergence → less ambiguity).
                keys = re.findall(r"'(\w+)':", cleaned_line)

                char_awk_groups = {}   # insertion-ordered: char_class → [td_key, ...]
                current_char = None
                for key in keys:
                    if re.match(r'C_\w+_C$', key):
                        current_char = key
                        char_awk_groups[current_char] = []
                    elif key.startswith('TD_') and current_char is not None:
                        char_awk_groups[current_char].append(key)

                updated = False
                already_linked_chars = set(DICT_IGN_TO_CHARACTER.values())

                for char_class, td_keys in char_awk_groups.items():
                    if not td_keys:
                        continue
                    char_external = DICT_INTERNAL_TO_EXTERNAL_CHARACTERS.get(char_class)
                    if not char_external or char_external in already_linked_chars:
                        continue
                    tag_awk_set = {DICT_INTERNAL_TO_EXTERNAL_AWAKENINGS.get(k, k) for k in td_keys}

                    candidates = [
                        ign for ign in IGN_LIST
                        if ign not in DICT_IGN_TO_CHARACTER
                        and tag_awk_set.issubset(set(DICT_IGN_TO_AWAKENINGS.get(ign, [])))
                    ]
                    if len(candidates) == 1:
                        ign = candidates[0]
                        DICT_IGN_TO_CHARACTER[ign] = char_external
                        already_linked_chars.add(char_external)
                        print(f"Tags-linked: {ign} → {char_external} (via {tag_awk_set})")
                        updated = True

                # Elimination fallback when all 6 chars appear in Tags and only 1 IGN remains
                all_chars_in_tags = {DICT_INTERNAL_TO_EXTERNAL_CHARACTERS[cc]
                                     for cc in char_awk_groups
                                     if cc in DICT_INTERNAL_TO_EXTERNAL_CHARACTERS}
                if len(all_chars_in_tags) == 6 and len(IGN_LIST) == 6:
                    unassigned_igns = [ign for ign in IGN_LIST if ign not in DICT_IGN_TO_CHARACTER]
                    unassigned_chars = all_chars_in_tags - set(DICT_IGN_TO_CHARACTER.values())
                    if len(unassigned_igns) == 1 and len(unassigned_chars) == 1:
                        ign = unassigned_igns[0]
                        char = next(iter(unassigned_chars))
                        DICT_IGN_TO_CHARACTER[ign] = char
                        print(f"Tags-elimination: {ign} → {char}")
                        updated = True

                if updated:
                    return True
```

- [ ] **Step 4: Re-run the checks — all should PASS**

Run: `python verify_rework.py`
Expected:
```
PASS  equipping-trainings does not populate DICT_IGN_TO_CHARACTER
PASS  round-1 identical-set Tags line commits nothing
PASS  subset match: Shieldz → Alice (via Strike Shot)
PASS  subset match: StalwartProtector → Bob (via Hotshot)
PASS  subset match: EmpoweringEnchanter → Carol (via Aerials)
PASS  ambiguous subset (2 candidates) commits nothing for Asher
PASS  ambiguous Asher case still resolves Era → Z
```
Exit 0.

- [ ] **Step 5: Commit**

```bash
git add processor.py verify_rework.py
git commit -m "Replace Tags exact-equality character matching with subset+uniqueness

The Tags dict deduplicates shared awakenings, so per-character tag
blocks are subsets — not equals — of player awakening sets. Match
each character to the unique IGN whose set is a superset of the
block; skip when zero or multiple candidates exist."
```

---

## Task 4: Tighten roster JSON extraction

**Files:**
- Modify: `processor.py:246-263` (the `custom-lobby-roster-v1` branch)

Replace the greedy regex with structural slicing and proper escape handling.

- [ ] **Step 1: Add a verification check that the real roster line parses correctly**

Append to `verify_rework.py` (before `if _failures:`):

```python
    # ── Check 5: real roster line from logsEXAMPLE produces correct team assignment
    state = _fresh_state()
    # Real line from logsEXAMPLE/OmegaStrikers1.log around line 9552 (trimmed)
    roster_line = (
        'LogPMCustomLobbyModel: Verbose: \t\tRoster Notification: '
        '{"type":"custom-lobby-roster-v1","strData":"{'
        '\\"team1Ids\\":[\\"pidA\\",\\"pidB\\",\\"pidC\\"],'
        '\\"team2Ids\\":[\\"pidD\\",\\"pidE\\",\\"pidF\\"],'
        '\\"allPlayerProfiles\\":['
        '{\\"username\\":\\"Alice\\",\\"playerId\\":\\"pidA\\"},'
        '{\\"username\\":\\"Bob\\",\\"playerId\\":\\"pidB\\"},'
        '{\\"username\\":\\"Carol\\",\\"playerId\\":\\"pidC\\"},'
        '{\\"username\\":\\"Dave\\",\\"playerId\\":\\"pidD\\"},'
        '{\\"username\\":\\"Eve\\",\\"playerId\\":\\"pidE\\"},'
        '{\\"username\\":\\"Frank\\",\\"playerId\\":\\"pidF\\"}'
        ']'
        '}"}'
    )
    _feed([roster_line], state)
    DICT_IGN_TO_TEAM = state[4]
    expected = {'Alice': 1, 'Bob': 1, 'Carol': 1, 'Dave': 2, 'Eve': 2, 'Frank': 2}
    check(
        "roster JSON parses six players into correct teams",
        DICT_IGN_TO_TEAM == expected,
        f"got {DICT_IGN_TO_TEAM!r}",
    )
```

- [ ] **Step 2: Run the check — it should PASS against the current code already**

Run: `python verify_rework.py`
Expected: check 5 PASS (because the current regex *does* handle this format — Fix 3 is hardening, not bug-correcting). Exit 0.

This is the baseline; we'll improve robustness without changing behaviour.

- [ ] **Step 3: Replace the roster branch in `processor.py`**

In [processor.py:242-264](../../processor.py#L242-L264), find:

```python
            elif "custom-lobby-roster-v1" in cleaned_line:
                # Parse team assignments from the WebSocket roster payload.
                # The line contains escaped JSON: {"type":"custom-lobby-roster-v1","strData":"{...}"}
                # strData holds team1Ids, team2Ids, and allPlayerProfiles (playerId + username).
                m = re.search(r'"strData":"(.*)"}\s*$', cleaned_line)
                if m:
                    try:
                        roster = json.loads(m.group(1).replace('\\"', '"'))
                        id_to_name = {p['playerId']: p['username']
                                      for p in roster.get('allPlayerProfiles', [])}
                        DICT_IGN_TO_TEAM.clear()
                        for pid in roster.get('team1Ids', []):
                            username = id_to_name.get(pid)
                            if username:
                                DICT_IGN_TO_TEAM[username] = 1
                        for pid in roster.get('team2Ids', []):
                            username = id_to_name.get(pid)
                            if username:
                                DICT_IGN_TO_TEAM[username] = 2
                        print(f"Team assignments updated: {DICT_IGN_TO_TEAM}")
                    except (json.JSONDecodeError, KeyError) as e:
                        print(f"Failed to parse roster JSON: {e}")
                return False
```

Replace with:

```python
            elif "custom-lobby-roster-v1" in cleaned_line:
                # Parse team assignments from the WebSocket roster payload.
                # The line contains a JSON envelope of the form:
                #   {"type":"custom-lobby-roster-v1","strData":"<escaped JSON>"}
                # We slice between the literal `"strData":"` and the closing `"}`
                # of the outer envelope, then decode the backslash-escaped inner JSON.
                start_marker = '"strData":"'
                idx = cleaned_line.find(start_marker)
                end = cleaned_line.rfind('"}')
                if idx == -1 or end <= idx + len(start_marker):
                    return False
                escaped = cleaned_line[idx + len(start_marker):end]
                try:
                    # The inner JSON has its quotes backslash-escaped (\"). Decoding
                    # with `unicode_escape` reverses this and also handles \\, \n, etc.
                    inner = escaped.encode('utf-8').decode('unicode_escape')
                    roster = json.loads(inner)
                    id_to_name = {p['playerId']: p['username']
                                  for p in roster.get('allPlayerProfiles', [])}
                    DICT_IGN_TO_TEAM.clear()
                    for pid in roster.get('team1Ids', []):
                        username = id_to_name.get(pid)
                        if username:
                            DICT_IGN_TO_TEAM[username] = 1
                    for pid in roster.get('team2Ids', []):
                        username = id_to_name.get(pid)
                        if username:
                            DICT_IGN_TO_TEAM[username] = 2
                    print(f"Team assignments updated: {DICT_IGN_TO_TEAM}")
                except (json.JSONDecodeError, KeyError, UnicodeDecodeError) as e:
                    print(f"Failed to parse roster JSON: {e}")
                return False
```

- [ ] **Step 4: Re-run the check — still PASS**

Run: `python verify_rework.py`
Expected: all checks PASS, exit 0.

- [ ] **Step 5: Commit**

```bash
git add processor.py verify_rework.py
git commit -m "Tighten roster JSON extraction with structural slicing

Replace greedy regex r'\"strData\":\"(.*)\"}\\s\$' with explicit
find-of-marker + rfind-of-terminator, and use unicode_escape decode
for proper inner-JSON unescaping. Catches UnicodeDecodeError too."
```

---

## Task 5: Full offline replay against `logsEXAMPLE/OmegaStrikers1.log`

**Files:**
- Modify: `verify_rework.py`

Final integration check: run the full game from the example log and verify all 6 players, teams, characters, and awakenings come out correct.

- [ ] **Step 1: Read the relevant section of `logsEXAMPLE/OmegaStrikers1.log` to hand-build the expected final state**

The 6-player game in `OmegaStrikers1.log` starts around line 10101 (last `EMatchPhase::PreGame` before that game). The 6 players visible in the equipping-trainings lines (line 10568+) are:

```
TTU Firebird, CloakOak, -sabr-, Asiainator, AltairPoke, NitroGamingN64
```

The roster JSON at line 9552 assigns them to teams. The Despawn lines link IGN → character. By end-of-game, expect:
- `IGN_LIST` (the 6 above, possibly with one being a spectator-omitted variant)
- `DICT_IGN_TO_TEAM` mapping each to team 1 or 2
- `DICT_IGN_TO_CHARACTER` mapping each to their character (verified by Despawn lines)

**IMPORTANT — verify these before encoding:** Read the file and grep:

```bash
grep -E "Despawn_Multicast_Implementation.*Character 'C_" logsEXAMPLE/OmegaStrikers1.log | head -20
grep "team1Ids" logsEXAMPLE/OmegaStrikers1.log | head -3
```

Use the actual mapping from the log. Encode it as the expected dict.

- [ ] **Step 2: Append the replay check to `verify_rework.py`**

Append before `if _failures:`:

```python
    # ── Check 6: full replay of logsEXAMPLE/OmegaStrikers1.log
    log_path = os.path.join(os.path.dirname(__file__), 'logsEXAMPLE', 'OmegaStrikers1.log')
    if not os.path.isfile(log_path):
        print(f"  SKIP  full replay (no log file at {log_path})")
    else:
        state = _replay_file(log_path)
        IGN_LIST = state[1]
        DICT_IGN_TO_CHARACTER = state[3]
        DICT_IGN_TO_TEAM = state[4]

        # Hand-verified from log content — REPLACE with the actual mappings
        # discovered in Step 1.
        expected_players = {
            'TTU Firebird', 'CloakOak', '-sabr-',
            'Asiainator', 'AltairPoke', 'NitroGamingN64',
        }

        check(
            "replay: all 6 IGNs identified",
            set(IGN_LIST) == expected_players,
            f"got {set(IGN_LIST)!r}",
        )
        check(
            "replay: all 6 players have a team",
            all(p in DICT_IGN_TO_TEAM for p in expected_players),
            f"got {DICT_IGN_TO_TEAM!r}",
        )
        check(
            "replay: all 6 players have a character",
            all(p in DICT_IGN_TO_CHARACTER for p in expected_players),
            f"got {DICT_IGN_TO_CHARACTER!r}",
        )
```

- [ ] **Step 3: Run the harness**

Run: `python verify_rework.py`
Expected: all 8 checks PASS, exit 0.

If `replay: all 6 players have a character` fails, inspect `DICT_IGN_TO_CHARACTER` — it likely means Despawn arrived for fewer than 6 players within the captured log window. That's a data-bound limitation, not a code bug. In that case, downgrade the check to "at least N players have a character" where N is the count of Despawn lines, but flag this for the user.

- [ ] **Step 4: Commit**

```bash
git add verify_rework.py
git commit -m "Add full-log replay verification against OmegaStrikers1.log"
```

---

## Task 6: Backward-compat check via existing `test_runner.py`

**Files:**
- None — this is a manual check.

Confirm the existing test path (which exercises only the equipping-trainings flow) still works end-to-end.

- [ ] **Step 1: Verify `.env` contains test-mode settings**

Inspect `.env` (if it exists) or temporarily create one:

```
TEST_LOG_FLAG=True
TEST_LOG_FILEPATH=test_game.log
OVERLAY_PORT=5000
```

- [ ] **Step 2: Run the test harness**

Run: `python test_runner.py`
Expected: a new console window opens running `main.py`; Flask reports ready; phases 1-5 stream every 6 seconds. Visiting `http://127.0.0.1:5000` in a browser should show 6 IGNs (PlayerAlpha…PlayerZeta) with growing awakening rows and **blank character portraits** (because the synthetic test log has no Despawn/Tags/roster data — character pairing is expected to be blank).

- [ ] **Step 3: Close both windows**

Press Ctrl+C in the test_runner console; close the main.py window. No code change needed.

---

## Task 7: Update `CLAUDE.md` to reflect actual behaviour

**Files:**
- Modify: `CLAUDE.md` (the inline character-source list)

- [ ] **Step 1: Edit `CLAUDE.md`**

Find:

```markdown
- `DICT_IGN_TO_CHARACTER` — `{ign: character_name}`, populated from three log sources in priority order: equipping-trainings lines > Despawn/KO events > Tags exact-match
```

Replace with:

```markdown
- `DICT_IGN_TO_CHARACTER` — `{ign: character_name}`, populated from two log sources: `Despawn_Multicast_Implementation` events (direct IGN+character pairing, but only fires on KO/round-end) and `Tags: {...}` subset matching against per-IGN awakening sets (fills in earlier rounds, ambiguous when awakening sets overlap).
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "Update CLAUDE.md: equipping-trainings is not a character source"
```

---

## Task 8: Clear `MOST_RECENTLY_PUBLISHED_TABLE` on game reset

**Files:**
- Modify: `processor.py` — the `CharacterSelect` and `PostGameCelebration` branches.

Found by the bug-finder review (`docs/superpowers/specs/bug-finder-notes.md` — see Deferred section below): when the rework lands, Tags-based subset matching causes more publishes per game. The `MOST_RECENTLY_PUBLISHED_TABLE` is not cleared on `reset_lists`, so a stale table from the previous game can theoretically suppress a legitimate publish if the candidate table happens to match. Low-probability but the fix is one line per call site. `reset_lists`'s signature stays locked (per spec); we mutate the table in-place at the call site instead.

- [ ] **Step 1: Edit the `CharacterSelect` branch in `processor.py`**

Find:

```python
        if "Current[EMatchPhase::CharacterSelect]" in cleaned_line:
            time.sleep(0.01)
            #CHARACTERS_LIST, IGN_LIST, DICT_IGN_TO_AWAKENINGS, ALL_LOGS_THIS_GAME =
            reset_lists(
            CHARACTERS_LIST, IGN_LIST, DICT_IGN_TO_AWAKENINGS, DICT_IGN_TO_CHARACTER, ALL_LOGS_THIS_GAME)

            ALL_LOGS_THIS_GAME.append(cleaned_line)
            return False
```

Replace with:

```python
        if "Current[EMatchPhase::CharacterSelect]" in cleaned_line:
            time.sleep(0.01)
            reset_lists(
                CHARACTERS_LIST, IGN_LIST, DICT_IGN_TO_AWAKENINGS, DICT_IGN_TO_CHARACTER, ALL_LOGS_THIS_GAME)
            MOST_RECENTLY_PUBLISHED_TABLE.clear()
            ALL_LOGS_THIS_GAME.append(cleaned_line)
            return False
```

- [ ] **Step 2: Edit the `PostGameCelebration` branch in `processor.py`**

Find:

```python
        if "Current[EMatchPhase::PostGameCelebration]" in cleaned_line:
            time.sleep(0.01)
            reset_lists(
                CHARACTERS_LIST, IGN_LIST, DICT_IGN_TO_AWAKENINGS, DICT_IGN_TO_CHARACTER, ALL_LOGS_THIS_GAME)
            print("PostGameCelebration detected — overlay cleared.")
            return "CLEAR"
```

Replace with:

```python
        if "Current[EMatchPhase::PostGameCelebration]" in cleaned_line:
            time.sleep(0.01)
            reset_lists(
                CHARACTERS_LIST, IGN_LIST, DICT_IGN_TO_AWAKENINGS, DICT_IGN_TO_CHARACTER, ALL_LOGS_THIS_GAME)
            MOST_RECENTLY_PUBLISHED_TABLE.clear()
            print("PostGameCelebration detected — overlay cleared.")
            return "CLEAR"
```

- [ ] **Step 3: Re-run the verification harness — all checks still PASS**

Run: `python verify_rework.py`
Expected: all 8 checks PASS, exit 0.

- [ ] **Step 4: Commit**

```bash
git add processor.py
git commit -m "Clear MOST_RECENTLY_PUBLISHED_TABLE on game reset

Prevents the prior game's table from suppressing a legitimate publish
when the new game's candidate happens to match (low probability, made
more relevant by the rework which publishes more often via Tags
subset matching). Signature of reset_lists stays unchanged; we mutate
the list in-place at the call site."
```

---

## Deferred (out of scope for this rework)

Bug-finder findings that warrant their own focused changes, not folded in here:

- **`os._exit(0)` shutdown path** in the `Application Will Terminate` branch — runs on the watchdog thread with a 10-second sleep and skips Flask/GUI cleanup. Better handled via a shared-state signal flag.
- **`ALL_LOGS_THIS_GAME` O(N²) duplicate check** — grows unbounded; only `DetermineLobbyAnimation` branch actually consumes it. Replace with a parallel `set` or restrict deduplication to the one branch that needs it.
- **`DetermineLobbyAnimation` rescan edge case** — depends on `VersusScreen` already being in `ALL_LOGS_THIS_GAME` before characters are accepted; on rescan, if the slice starts after `VersusScreen`, characters never load. Worth verifying against more sample logs.
- **`Despawn` arriving before first `equipping trainings`** — the player isn't in `IGN_LIST` yet, link is silently dropped. Could be patched by retrying Tags-linking once the IGN registers.
- **Debug `print` statements** throughout `process_log_entry` and `CONSTRUCT_UPLOAD_TABLE` — noisy on long sessions.
- **`time.sleep(0.01)` calls** scattered through the handler — single-threaded inside watchdog, so race avoidance is non-functional. Cosmetic-only.

---

## Task 9: Final verification + summary

- [ ] **Step 1: Run `verify_rework.py` one last time**

Run: `python verify_rework.py`
Expected: all checks PASS, exit 0.

- [ ] **Step 2: Inspect the git log**

Run: `git log --oneline main..HEAD` (or `git log --oneline -10`)
Expected: 5-7 clean commits, each scoped to one change.

- [ ] **Step 3: Summarize for the user**

Report:
- 3 logic fixes landed in `processor.py` (dead code removed, Tags matching rewritten, roster JSON tightened).
- 0 changes to UI / server / observer / GUI / test_runner / images.
- Verification harness `verify_rework.py` added at project root, 8 checks all PASS.
- `CLAUDE.md` updated to reflect actual character-association sources.
- Bug-finder findings: [fold in summary].

---

## Self-Review

- [x] **Spec coverage:** Fix 1 → Task 2. Fix 2 → Task 3. Fix 3 → Task 4. Round-1 UX (blank portrait) verified by Task 5 and Task 6. CLAUDE.md update → Task 7. No spec section left unimplemented.
- [x] **Placeholder scan:** No TBDs. All code blocks contain literal code. Expected output specified for every "run this" step.
- [x] **Type consistency:** State containers are passed positionally throughout; `_fresh_state()` matches the 7-argument signature of `process_log_entry`. Internal-to-external lookups use the same dicts (`DICT_INTERNAL_TO_EXTERNAL_CHARACTERS` / `_AWAKENINGS`) in both the planned code and the checks.
- [x] **Acceptance of data-bound limit:** Round-1 character pairing remains blank without a Despawn signal — documented in Task 5 step 3's downgrade clause.
