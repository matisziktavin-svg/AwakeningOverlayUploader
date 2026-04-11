import re
import json
import time
import sys
import os
from collections import OrderedDict

# Keywords to filter log entries
KEYWORDS = ["Application Will Terminate", "PostGameCelebration", "Tags: {'", "equipping trainings", "Num Trainings: 2"]
KEYWORDS.extend(["EMatchPhase::VersusScreen", "LogPMSkinDataManager: UPMSkinDataManagerComponent::DetermineLobbyAnimation",
"EMatchPhase::CharacterSelect"])  # Marks the start of a new game
KEYWORDS.append("APMCharacter::Despawn_Multicast_Implementation")  # Links character class to player IGN
KEYWORDS.append("custom-lobby-roster-v1")  # Roster updates — used to assign players to teams



DICT_INTERNAL_TO_EXTERNAL_CHARACTERS = {
    "C_AngelicSupport_C": "Atlas", "C_ChaoticRocketeer_C": "Luna", "C_CleverSummoner_C": "Juno",
    "C_EDMOni_C": "Octavia", "C_EmpoweringEnchanter_C": "Era", "C_FlashySwordsman_C": "Zentaro",
    "C_FlexibleBrawler_C": "Juliette", "C_GravityMage_C": "Finii", "C_HulkingBeast_C": "X",
    "C_MagicalPlaymaker_C": "Ai.Mi", "C_ManipulatingMastermind_C": "Rune", "C_NimbleBlaster_C": "Drek'ar",
    "C_RockOni_C": "Vyce", "C_Shieldz_C": "Asher", "C_SpeedySkirmisher_C": "Kai",
    "C_StalwartProtector_C": "Dubu", "C_TempoSniper_C": "Estelle", "C_UmbrellaUser_C": "Kazan",
    "C_WhipFighter_C": "Rasmus", "C_Healer_C": "Nao", "C_DrumOni_C": "Mako",



    "AngelicSupport": "Atlas", "ChaoticRocketeer": "Luna", "CleverSummoner": "Juno",
    "EDMOni": "Octavia", "EmpoweringEnchanter": "Era", "FlashySwordsman": "Zentaro",
    "FlexibleBrawler": "Juliette", "GravityMage": "Finii", "HulkingBeast": "X",
    "MagicalPlaymaker": "Ai.Mi", "ManipulatingMastermind": "Rune", "NimbleBlaster": "Drek'ar",
    "RockOni": "Vyce", "ShieldUser": "Asher", "SpeedySkirmisher": "Kai",
    "StalwartProtector": "Dubu", "TempoSniper": "Estelle", "UmbrellaUser": "Kazan",
    "WhipFighter": "Rasmus", "Healer": "Nao", "DrumOni": "Mako",
}      #the bottom dict is used for extracting logs from
        #lines with "LogPMSkinDataManager: UPMSkinDataManagerComponent::DetermineLobbyAnimation"
        #for whatever reason Asher's is different between the top and bottom.

DICT_INTERNAL_TO_EXTERNAL_AWAKENINGS = {"TD_AvoidDamageHitHarder": "Glass Cannon", "TD_BarrierBuff": "Demolitionist", "TD_BaseStaggerAndRegen": "Reptile Remedy", "TD_BlessingCooldownRate": "Spark of Focus", "TD_BlessingMaxStagger": "Spark of Resilience", "TD_BlessingPower": "Spark of Strength", "TD_BlessingShare": "Spark of Leadership", "TD_BlessingSpeed": "Spark of Agility", "TD_BuffAndDebuffDuration": "Cast to Last", "TD_ComboATarget": "One-Two Punch", "TD_CreationSize": "Monumentalist", "TD_CreationSizeLifeTime": "Timeless Creator", "TD_DistancePower": "Deadeye", "TD_EdgePower": "Knife's Edge", "TD_EmpoweredHitsBuff": "Specialized Training", "TD_EnergyCatalyst": "Catalyst", "TD_EnergyConversion": "Egoist", "TD_EnergyDischarge": "Fire Up!", "TD_EnhancedOrbsCooldown": "Orb Ponderer" , "TD_EnhancedOrbsSpeed": "Orb Dancer", "TD_FasterDashes": "Super Surge", "TD_FasterDashes2": "Chronoboost", "TD_FasterDashes3": "Explosive Entrance", "TD_FasterProjectiles": "Missile Propulsion", "TD_FasterProjectiles2": "Aerials", "TD_FasterProjectiles3":"Siege Machine", "TD_HitAnythingRestoreStagger": "Tempo Swing", "TD_HitEnemyBurnThem": "Stinger", "TD_HitRockCooldown": "Hotshot", "TD_HitsIncreaseSpeedAndPower": "Stacks On Stacks", "TD_HitSpeed": "Fight Or Flight", "TD_HitsReduceCooldowns": "Perfect Form", "TD_IncreasedPowerWithMaxStagger": "OLD Unstoppable", "TD_IncreasedSpeedWithStagger": "Stagger Swagger", "TD_KOKing": "Prize Fighter", "TD_MovementAbilityCharges": "Twin Drive", "TD_MultiHitsReduceCooldowns": "Heavy Impact", "TD_OrbShare": "Orb Replicator", "TD_PrimaryAbilityCooldownReduction": "Rapid Fire", "TD_PrimaryEcho": "Primetime", "TD_ResistFirstHit": "Unstoppable", "TD_Revive":"Recovery Drone", "TD_ShrinkSelfGrowAllies": "Among Titans", "TD_SizeIncrease": "Built Different", "TD_SizeIncrease2": "Big Fish", "TD_SizePowerConversion": "Might of the Colossus", "TD_SpecialCooldownAfterRounds": "Extra Special", "TD_StackingSize": "Rampage", "TD_StaggerCooldownRateConversion": "Reverberation", "TD_StaggerPowerConversion": "Bulk Up", "TD_StaggerSpeedConversion": "Peak Performance", "TD_StrikeCooldownReduction": "Quick Strike", "TD_StrikeRockTowardsAllies": "Team Player", "TD_TakeDownReduceCooldowns": "Adrenaline Rush"}

DICT_INTERNAL_TO_EXTERNAL_AWAKENINGS.update({"TD_MovementAbilitiesTeleport": "Eject Button", "TD_IncreasedSpeedCrossingMidfield": "Magnetized Soles", "TD_GainRampingSpeed": "Momentum Boots", "TD_HitEnemyDrainThem": "Siphoning Wand", "TD_GoalArcPower": "Powerhouse Pauldrons", "TD_HitStaggerEnemyCooldownReduction": "Pummelers", "TD_StrikeRockSpeedUp": "Slick Kicks", "TD_RangedStrike": "Strike Shot", "TD_KnockAnythingRecoverStagger": "Vicious Vambraces" })
DICT_INTERNAL_TO_EXTERNAL_AWAKENINGS.update({"TD_IncreasedStatsWhileStaggered": "Berserker", "TD_AvoidKnockoutGainSpeed": "Omega Infused Accelerator", "TD_HitCoreGainCDR": "Inner Focus"})




def process_log_entry(line,
CHARACTERS_LIST,
IGN_LIST,
DICT_IGN_TO_AWAKENINGS,
DICT_IGN_TO_CHARACTER,
DICT_IGN_TO_TEAM,
ALL_LOGS_THIS_GAME,
MOST_RECENTLY_PUBLISHED_TABLE
):
    # Clean and filter log entry
    cleaned_line = re.sub(r'^\[.*?\]\[.*?\]', '', line).strip()
    if any(keyword in cleaned_line for keyword in KEYWORDS):



        #print(cleaned_line)

        # Soft reset if new game is detected
        #time.sleep(0.01)
        if "Current[EMatchPhase::CharacterSelect]" in cleaned_line:
            time.sleep(0.01)
            #CHARACTERS_LIST, IGN_LIST, DICT_IGN_TO_AWAKENINGS, ALL_LOGS_THIS_GAME =
            reset_lists(
            CHARACTERS_LIST, IGN_LIST, DICT_IGN_TO_AWAKENINGS, DICT_IGN_TO_CHARACTER, ALL_LOGS_THIS_GAME)

            ALL_LOGS_THIS_GAME.append(cleaned_line)
            return False

        # Avoid duplicate log entries
        if cleaned_line not in ALL_LOGS_THIS_GAME:
            if("LogPMSkinDataManager: UPMSkinDataManagerComponent::DetermineLobbyAnimation" in cleaned_line):
                #then we need to check if EMatchPhase::VersusScreen is a substring in an element of ALL_LOGS_THIS_GAME which is a list of strings.
                if(any("EMatchPhase::VersusScreen" in log_line for log_line in ALL_LOGS_THIS_GAME)== False): #check

                    return False#if EmatchPhase::VersusScreen is not in the logs, then we should not append the current line.

            ALL_LOGS_THIS_GAME.append(cleaned_line)
            #time.sleep(0.1)
            #self.update_signal.emit(cleaned_line)  # Emit signal for new log entry

            # Extract character tags and convert to external names

            if "LogPMSkinDataManager: UPMSkinDataManagerComponent::DetermineLobbyAnimation" in cleaned_line:
                if(len(CHARACTERS_LIST)<6):
                    #print(f"line 109 Characters in the lobby so far {CHARACTERS_LIST}")
                    converted_value = None
                    match = re.search(r"SD_([^_]+)", cleaned_line)
                    if match:
                        extracted_value = match.group(1)
                        converted_value = DICT_INTERNAL_TO_EXTERNAL_CHARACTERS.get(extracted_value)

                    # Optionally, handle the case where the key might not exist
                    if converted_value is None:
                        return
                    else:
                        print("Converted value:", converted_value)
                        CHARACTERS_LIST.append(converted_value)
                        if(len(CHARACTERS_LIST)>5):
                            time.sleep(0.01)
                            print(cleaned_line)
                            #for a in ALL_LOGS_THIS_GAME:
                            #    print(a)
                            print(f"all 6 characters in the lobby: {CHARACTERS_LIST}")
                            return True
                            #print(ALL_LOGS_THIS_GAME)
                            #we should upload. TODO
                            #self.update_signal.emit("update_characters_display")  # Emit signal to update characters
            # Update player trainings with external names
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
                    existing_trainings = DICT_IGN_TO_AWAKENINGS.get(player, [])  # Use get to avoid KeyError

                    if existing_trainings == trainings:

                        return False
                        #print(f"Trainings for player {player} have not changed.")
                    else:
                        # Update the trainings list and trigger the function
                        time.sleep(0.01)
                        #print(f"Trainings for player {player} have changed.")
                        #print(127)
                        #print(trainings)
                        DICT_IGN_TO_AWAKENINGS[player] = trainings
                        #DICT_IGN_TO_AWAKENINGS = OrderedDict(sorted(DICT_IGN_TO_AWAKENINGS.items()))
                        #print(137)
                        #print(DICT_IGN_TO_AWAKENINGS)
                        #we should consider uploading, return True
                        return True

            elif "Tags: {'" in cleaned_line:
                # Tags lines emit keys in insertion order: each C_xxx_C key is immediately
                # followed by the TD_xxx awakenings that belong to that character, until the
                # next C_xxx_C key appears.  We exploit this ordering to match awakening sets
                # against DICT_IGN_TO_AWAKENINGS and link IGNs to their character without
                # needing a KO event.
                #
                # Elimination fallback (original behaviour) is kept: if exactly one IGN is
                # still unlinked and the Tags line contains all 6 characters, we can infer
                # the last assignment.
                keys = re.findall(r"'(\w+)':", cleaned_line)

                # Build char_class → [td_key, ...] from the ordered key sequence
                char_awk_groups = {}   # insertion-ordered dict (Python 3.7+)
                current_char = None
                for key in keys:
                    if re.match(r'C_\w+_C$', key):
                        current_char = key
                        char_awk_groups[current_char] = []
                    elif key.startswith('TD_') and current_char is not None:
                        char_awk_groups[current_char].append(key)

                updated = False
                for char_class, td_keys in char_awk_groups.items():
                    if not td_keys:
                        continue
                    char_external = DICT_INTERNAL_TO_EXTERNAL_CHARACTERS.get(char_class)
                    if not char_external:
                        continue
                    # Convert internal TD keys → external names (same format stored in DICT_IGN_TO_AWAKENINGS)
                    tag_awk_set = {DICT_INTERNAL_TO_EXTERNAL_AWAKENINGS.get(k, k) for k in td_keys}

                    for ign in IGN_LIST:
                        if DICT_IGN_TO_CHARACTER.get(ign) == char_external:
                            break  # already correctly linked
                        if ign in DICT_IGN_TO_CHARACTER:
                            continue  # already linked to a different character
                        ign_awks = set(DICT_IGN_TO_AWAKENINGS.get(ign, []))
                        if tag_awk_set and tag_awk_set.issubset(ign_awks):
                            DICT_IGN_TO_CHARACTER[ign] = char_external
                            print(f"Tags-linked: {ign} → {char_external} (via {tag_awk_set})")
                            updated = True
                            break

                # Elimination fallback when all 6 chars are present and only 1 IGN is unlinked
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

            elif "Despawn_Multicast_Implementation" in cleaned_line:
                # Format: Character 'C_StalwartProtector_C_2147407801' (Player 'TTU Firebird')
                # Fires on every KO and end-of-round; used to build DICT_IGN_TO_CHARACTER.
                # The Tags handler above can infer the last unlinked player by elimination.
                match = re.search(r"Character '(C_\w+_C)_\d+' \(Player '(.+?)'\)", cleaned_line)
                if match:
                    char_class = match.group(1)   # e.g. "C_StalwartProtector_C"
                    ign = match.group(2)           # e.g. "TTU Firebird"
                    char_external = DICT_INTERNAL_TO_EXTERNAL_CHARACTERS.get(char_class)
                    if char_external and ign in IGN_LIST:
                        if DICT_IGN_TO_CHARACTER.get(ign) != char_external:
                            DICT_IGN_TO_CHARACTER[ign] = char_external
                            print(f"Character linked: {ign} → {char_external}")
                            return True  # Trigger overlay re-publish

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

            elif "Application Will Terminate" in cleaned_line:
                time.sleep(0.01)
                #we should end app here TODO
                print(f"Omega Strikers is terminating log found. Closing this app in 10 seconds.")
                time.sleep(10)
                os._exit(0)


def return_true_if_should_upload(CHARACTERS_LIST, IGN_LIST, DICT_IGN_TO_AWAKENINGS,
DICT_IGN_TO_CHARACTER, ALL_LOGS_THIS_GAME, MOST_RECENTLY_PUBLISHED_TABLE):

    #checks if self.MOST_RECENTLY_PUBLISHED_TABLE is the same as what we would upload.

    #first, construct the table that we WOULD upload.
    candidate_table = CONSTRUCT_UPLOAD_TABLE(CHARACTERS_LIST, IGN_LIST, DICT_IGN_TO_AWAKENINGS, DICT_IGN_TO_CHARACTER)
    #FIRST COLUMN should be characters list

    #SECOND COLUMN should IGN LIST
    #THIRD COLUMN should be that corresponding IGN's


    #if MOST_RECENTLY_PUBLISHED_TABLE is the same as  the candidate,
    #@ we should not upload and return BOOLEAN_CONSIDER_UPLOAD false (?)


    #checks if CHARACTERS_LIST is 6, IGN_LIST is 6. if both are 6 we keep running this function.
    if(len(CHARACTERS_LIST)!= 6 or len(IGN_LIST)!= 6):
        return False

    if iterate_dict_values_true_if_lengths_are_equal(DICT_IGN_TO_AWAKENINGS) is False:
        return False
        #awakening list of each ign is uneven. return False.

    #check if MOST_RECENTLY_PUBLISHED_TABLE is the same as candidate table.
    if(MOST_RECENTLY_PUBLISHED_TABLE==candidate_table):
        return False

    return True



def iterate_dict_values_true_if_lengths_are_equal(DICT_IGN_TO_AWAKENINGS):
    lengths = [len(value) for value in DICT_IGN_TO_AWAKENINGS.values()]

    # Check if all lengths are the same
    return all(length == lengths[0] for length in lengths)
    #returns true if all are the same length.
    #returns false if something is uneven.

def CONSTRUCT_UPLOAD_TABLE(CHARACTERS_LIST, IGN_LIST, DICT_IGN_TO_AWAKENINGS, DICT_IGN_TO_CHARACTER=None):
    # Initialize the 2D table to store the rows
    upload_table = []
    print('construct_upload_table function called')
    print("DEBUG: CHARACTERS_LIST =", CHARACTERS_LIST)
    print("DEBUG: IGN_LIST =", IGN_LIST)
    print("DEBUG: DICT_IGN_TO_AWAKENINGS =", DICT_IGN_TO_AWAKENINGS)
    print("DEBUG: DICT_IGN_TO_CHARACTER =", DICT_IGN_TO_CHARACTER)

    # Build a reverse-lookup table: frozenset(awakenings) → character.
    # This uses the already-confirmed IGN→character + IGN→awakenings entries so that
    # any IGN whose C_xxx_C token was missing from the trainings line can still be
    # identified by matching their awakening set against a known character's set.
    ign_to_char = DICT_IGN_TO_CHARACTER if DICT_IGN_TO_CHARACTER else {}
    awakenings_to_character = {}
    for confirmed_ign, confirmed_char in ign_to_char.items():
        confirmed_awks = DICT_IGN_TO_AWAKENINGS.get(confirmed_ign, [])
        if confirmed_awks:
            awakenings_to_character[frozenset(confirmed_awks)] = confirmed_char

    # Iterate over IGNs (in natural arrival order).
    # Characters come from DICT_IGN_TO_CHARACTER (populated by equipping-trainings and
    # Despawn log lines). If an IGN is still missing, fall back to matching their
    # awakening set against the reverse-lookup built above.
    for ign in IGN_LIST:
        character = ign_to_char.get(ign, "")
        if not character:
            ign_awks = DICT_IGN_TO_AWAKENINGS.get(ign, [])
            if ign_awks:
                character = awakenings_to_character.get(frozenset(ign_awks), "")
        awakenings = DICT_IGN_TO_AWAKENINGS.get(ign, [])

        row = [character, ign] + awakenings
        while len(row) < 8:
            row.append("")
        upload_table.append(row)

    print(f"upload table:\n{upload_table}")
    return upload_table


def publish_state(shared_state,
                  CHARACTERS_LIST,
                  IGN_LIST,
                  DICT_IGN_TO_AWAKENINGS,
                  DICT_IGN_TO_CHARACTER,
                  DICT_IGN_TO_TEAM,
                  ALL_LOGS_THIS_GAME,
                  MOST_RECENTLY_PUBLISHED_TABLE):
    """
    Constructs the current game state table and pushes it to the overlay shared state.
    Returns the table on success, or None if construction failed.
    """
    table = CONSTRUCT_UPLOAD_TABLE(CHARACTERS_LIST, IGN_LIST, DICT_IGN_TO_AWAKENINGS, DICT_IGN_TO_CHARACTER)
    if table is None:
        return None

    players = [
        {
            "character": row[0],
            "ign": row[1],
            "awakenings": [a for a in row[2:] if a != ""],
            "team": DICT_IGN_TO_TEAM.get(row[1], 0),
        }
        for row in table
    ]
    shared_state.update(players)
    print("Overlay state updated.")
    return table

def reset_lists(CHARACTERS_LIST, IGN_LIST, DICT_IGN_TO_AWAKENINGS, DICT_IGN_TO_CHARACTER, ALL_LOGS_THIS_GAME):
    # DICT_IGN_TO_TEAM is intentionally NOT cleared here — team assignments come from the
    # lobby roster (before CharacterSelect) and must survive into the match. The next
    # lobby's roster notification will overwrite team data for the following game.

    print('RESETTING LIST. PRINTING DICT_IGN_TO_AWAKENINGS OF LAST GAME...')
    print(IGN_LIST)
    print(DICT_IGN_TO_AWAKENINGS)

    CHARACTERS_LIST.clear()
    IGN_LIST.clear()
    DICT_IGN_TO_AWAKENINGS.clear()
    DICT_IGN_TO_CHARACTER.clear()
    ALL_LOGS_THIS_GAME.clear()

