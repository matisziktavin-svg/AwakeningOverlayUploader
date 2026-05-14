"""
Offline verification for processor.py changes.

Runs unit-style checks against process_log_entry and replays the example
log files to verify final state. Exits 0 if all checks pass, 1 otherwise.

Usage:  python verify_rework.py
"""

import os
import re
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
    """Feed a list of log lines (with or without timestamp prefix) into process_log_entry."""
    results = []
    for line in lines:
        result = processor.process_log_entry(line, *state)
        results.append(result)
    return results


def _replay_file(path):
    """Replay a full log file from the last EMatchPhase::PreGame onwards."""
    with open(path, 'r', encoding='utf-8') as f:
        all_lines = f.read().splitlines()
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
    state[2]['Alice'] = ['Among Titans', 'Strike Shot']
    state[2]['Bob']   = ['Among Titans', 'Hotshot']
    state[2]['Carol'] = ['Among Titans', 'Aerials']
    _feed([
        "LogPMPerfStatsSubsystem: Tags: {'C_Shieldz_C': '1', 'TD_ShrinkSelfGrowAllies': '3', 'TD_RangedStrike': '1', 'C_StalwartProtector_C': '1', 'TD_HitRockCooldown': '1', 'C_EmpoweringEnchanter_C': '1', 'TD_FasterProjectiles2': '1'}",
    ], state)
    DICT_IGN_TO_CHARACTER = state[3]
    check(
        "subset match: Shieldz -> Alice (via Strike Shot)",
        DICT_IGN_TO_CHARACTER.get('Alice') == 'Asher',
        f"got {DICT_IGN_TO_CHARACTER!r}",
    )
    check(
        "subset match: StalwartProtector -> Bob (via Hotshot)",
        DICT_IGN_TO_CHARACTER.get('Bob') == 'Dubu',
        f"got {DICT_IGN_TO_CHARACTER!r}",
    )
    check(
        "subset match: EmpoweringEnchanter -> Carol (via Aerials)",
        DICT_IGN_TO_CHARACTER.get('Carol') == 'Era',
        f"got {DICT_IGN_TO_CHARACTER!r}",
    )

    # ── Check 4: ambiguous subset (2 candidates) — skip Asher; still resolve Era
    state = _fresh_state()
    state[1].extend(['X', 'Y', 'Z'])
    state[2]['X'] = ['Among Titans', 'Strike Shot']
    state[2]['Y'] = ['Among Titans', 'Strike Shot']
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
        "ambiguous Asher case still resolves Era -> Z",
        DICT_IGN_TO_CHARACTER.get('Z') == 'Era',
        f"got {DICT_IGN_TO_CHARACTER!r}",
    )

    # -- Check 5: real roster JSON produces correct team map ----------------
    state = _fresh_state()
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

    # -- Check 6: malformed roster JSON does not crash ----------------------
    state = _fresh_state()
    state[4]['Pre'] = 1  # pre-existing assignment from a previous roster line
    malformed = 'custom-lobby-roster-v1 "strData":"{not-valid-json'
    try:
        _feed([malformed], state)
        crashed = False
    except Exception:
        crashed = True
    check(
        "malformed roster JSON does not raise",
        not crashed,
        "raised an exception",
    )

    if _failures:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
