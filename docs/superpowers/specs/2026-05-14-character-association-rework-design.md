# Character-Association Rework — Design Spec

**Date:** 2026-05-14
**Scope:** `processor.py` only
**Out of scope:** UI (HTML/CSS/JS), server, observer, GUI, build, images, tests

## Problem statement

The overlay's mapping of `IGN → character` is unreliable, producing missing or wrong character portraits during round 1 and sometimes beyond. Three concrete failure modes in `processor.py`:

1. **Dead code in the equipping-trainings handler** ([`processor.py:133-141`](../../../processor.py#L133-L141)) attempts to extract a `C_X_C` token from the trainings list. That token never appears in those lines, so the branch never fires.
2. **Tags-line character linking uses exact set equality** ([`processor.py:163-225`](../../../processor.py#L163-L225)). The per-character grouping in the `Tags: {...}` dict is real, but the Tags dict deduplicates shared awakenings — so a character's per-character tag block is a *subset* of, not equal to, that player's full awakening list. Exact equality fails whenever any two players share an awakening (which they almost always do because of `StartingAwakenings`).
3. **Fragile roster JSON extraction** ([`processor.py:246-263`](../../../processor.py#L246-L263)) uses a greedy regex and incomplete escape handling. Works on the sampled data; brittle against future format variations.

## What the data actually supports

Verified by two research passes against `logsEXAMPLE/OmegaStrikers.log` and `logsEXAMPLE/OmegaStrikers1.log`:

| Data point | Source line | Reliability |
|---|---|---|
| Players (IGNs) | `Player '<IGN>' equipping trainings ...` | Clean — IGN named directly, one line per player per round |
| Team per player | `custom-lobby-roster-v1` JSON, `team1Ids` / `team2Ids` keyed by `playerId`, joined via `allPlayerProfiles[].username` | Clean |
| Awakenings per player | Same `equipping trainings` line; `re.findall(r"TD_\w+", rest)` | Clean — grows monotonically each round |
| Character per player | `Despawn_Multicast_Implementation - Character 'C_X_C_<inst>' (Player '<IGN>')` | Reliable but **late** — only fires on KO/round-end |
| Character per player (supplemental) | `Tags: {...}` per-character grouped tag dict | Reliable from round 2 onward via subset matching; **blind in round 1** if all players share starting awakenings |

**No earlier IGN↔character signal exists.** A focused secondary search ruled out `CharacterSelect`-phase events, `OnRep_*` lines, `PossessedBy`, lobby pick notifications, and `LogPMSkinDataManager InitData` (which fires earlier but does not name the IGN). Round-1 character pairing is therefore data-bound: it cannot precede the first Despawn or the first round-2 awakening pick.

## Design

### Fix 1 — Remove dead character-extraction branch

In the `equipping trainings` handler, delete the `re.search(r'(C_\w+_C)(?:_\d+)?', match.group(2))` block and the `DICT_IGN_TO_CHARACTER[player] = char_external` assignment that follows it. The trainings list portion (`match.group(2)`) contains only `TrainingData:TD_X , TrainingData:TD_Y , ...` tokens; no character class will ever appear there. Removing this branch eliminates dead code and clarifies that `DICT_IGN_TO_CHARACTER` is populated only by Despawn and Tags.

Also delete the CLAUDE.md claim in the project documentation that lists equipping-trainings as the primary character source. (Documentation edit is out of scope for the `processor.py` change itself but is noted in the implementation plan.)

### Fix 2 — Subset matching with uniqueness check for Tags linking

The `Tags: {...}` dict is a deduplicated multiset of GameplayTags currently active across all 6 characters. Its iteration order groups tags per-character: each `C_X_C` key is followed by `TD_X` keys belonging to that character, *until the next `C_X_C` key appears*. When two players share an awakening, the awakening's `TD_X` key appears once, under whichever character was iterated first. Characters whose entire awakening set is shared with earlier-iterated characters therefore appear with zero tags.

The consequence: for each character C with non-empty tag awakenings `T_C`, **`T_C` is a subset of the awakening set of exactly one player** — namely, the player playing C. The other players whose sets are supersets of `T_C` do not exist (because if another player's set contained all of `T_C`, that player's character would also have to contain those tags, but tags are deduplicated to the earliest character).

The new logic:

```
for each (char_class, td_keys) in char_awk_groups.items() where td_keys is non-empty:
    char_external = lookup(char_class)
    if char_external is None: continue
    if char_external is already linked to an IGN: continue
    tag_awk_set = {lookup(k) for k in td_keys}

    candidates = [ign for ign in IGN_LIST
                  if ign not in DICT_IGN_TO_CHARACTER
                  and tag_awk_set.issubset(set(DICT_IGN_TO_AWAKENINGS.get(ign, [])))]

    if len(candidates) == 1:
        DICT_IGN_TO_CHARACTER[candidates[0]] = char_external
        updated = True
    # otherwise (0 or >1) skip — wait for more data
```

Keep the existing elimination fallback (when all 6 characters appear in Tags and only 1 IGN is unlinked, fill by exclusion).

This logic gracefully degrades through the game:

- **Round 1, before first pick:** all players have only `StartingAwakenings`. Subset matching always finds 0 or 6 candidates → nothing committed. Despawn remains the only path. Acceptable: blank character images until first KO.
- **Round 1, after first pick:** players have `{starting + first pick}`. If picks diverge across the 6 players, subset matching commits unambiguous links. If two players share a round-1 pick, those two stay ambiguous; the other 4 link cleanly.
- **Round 2+:** divergence increases; subset matching converges to full coverage in nearly all real games.

### Fix 3 — Robust roster JSON extraction

Replace the greedy regex `r'"strData":"(.*)"}\s*$'` with:

```python
idx = cleaned_line.find('"strData":"')
if idx == -1:
    return False
start = idx + len('"strData":"')
# strData runs to the closing `"` immediately before the closing `}` of the outer envelope
end = cleaned_line.rfind('"}')
if end <= start:
    return False
escaped = cleaned_line[start:end]
roster = json.loads(escaped.encode('utf-8').decode('unicode_escape'))
```

This is structural slicing (not regex back-tracking) and uses the same `unicode_escape` decode that Python's standard library uses internally for JSON-in-JSON. Falls back gracefully on `json.JSONDecodeError`.

## What does NOT change

- Public API: `process_log_entry`, `return_true_if_should_upload`, `publish_state`, `CONSTRUCT_UPLOAD_TABLE`, `reset_lists`, `iterate_dict_values_true_if_lengths_are_equal` — signatures unchanged.
- LogHandler state shape: `IGN_LIST`, `CHARACTERS_LIST`, `DICT_IGN_TO_AWAKENINGS`, `DICT_IGN_TO_CHARACTER`, `DICT_IGN_TO_TEAM`, `ALL_LOGS_THIS_GAME`, `MOST_RECENTLY_PUBLISHED_TABLE` — unchanged.
- All other parsing branches (`CharacterSelect`, `PostGameCelebration`, `DetermineLobbyAnimation`, `Despawn`, `Application Will Terminate`) — unchanged.
- All lookup dicts (`DICT_INTERNAL_TO_EXTERNAL_CHARACTERS`, `DICT_INTERNAL_TO_EXTERNAL_AWAKENINGS`) — unchanged.
- Files: `main.py`, `observer.py`, `overlay_server.py`, `gui.py`, `templates/overlay.html`, `test_runner.py`, `AwakeningOverlayUploader.spec`, all image directories — untouched.
- Round-1 UX: blank character portrait until disambiguation. No HTML/CSS/JS edits.

## Verification

1. **Backward-compatibility check:** `test_runner.py` runs (no Tags lines, no Despawn, no roster — exercises the equipping-trainings → publish path only). Behaviour must be identical to today: 6 players appear with names + awakenings, character portraits blank (because no Despawn/Tags input is provided).
2. **Replay check:** offline-feed both `logsEXAMPLE/*.log` files line-by-line through the new `process_log_entry` and inspect the final state:
   - All 6 IGNs in `IGN_LIST`
   - All 6 teams in `DICT_IGN_TO_TEAM` (where roster is present)
   - All 6 characters in `DICT_IGN_TO_CHARACTER` by end-of-game (via Despawn + Tags combined)
   - Awakening lists match the equipping-trainings sequence
3. **No regression:** compare final `MOST_RECENTLY_PUBLISHED_TABLE` against current behaviour on each example log.

## Open risks

- **`StartingAwakenings` collision in round 1** is acknowledged and accepted as data-bound — blank portraits until first KO.
- **Bot / co-op matches** were not in the sample logs. If `equipping trainings` lines don't fire for AI players, the IGN list may be incomplete. Out of scope for this rework; flagged for future work.
- **Spectator POV vs player POV** — sample logs include spectator footage. If line formats differ structurally on player-POV logs, additional patterns may be needed. Out of scope for this rework; flagged for future work.

## Implementation plan

To be drafted via the `writing-plans` skill in the next step.
