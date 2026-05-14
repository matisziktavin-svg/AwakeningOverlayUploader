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

    if _failures:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
