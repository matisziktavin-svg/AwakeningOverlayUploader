"""
Test runner for AwakeningOverlayUploader.

Starts main.py automatically, then simulates a full match by writing log
entries to the test log file one round at a time.

Usage:
  1. In your .env set:
       TEST_LOG_FLAG=True
       TEST_LOG_FILEPATH=test_game.log
  2. Run:  python test_runner.py
     (that's it — main.py opens in a new window automatically)

Adjust ROUND_DELAY to control seconds between rounds.
"""

import os
import sys
import time
import subprocess
import urllib.request
from dotenv import load_dotenv

load_dotenv()

LOG_PATH    = os.getenv('TEST_LOG_FILEPATH', 'test_game.log')
PORT        = int(os.getenv('OVERLAY_PORT', '5000'))
ROUND_DELAY = 6  # seconds between rounds

# ── Log line prefix (stripped by the parser — content is what matters) ───────
T = "[2024.01.01-12.00.00:000][  0]"

PHASE_1 = f"""\
{T}LogGameMode: Current[EMatchPhase::CharacterSelect] Previous[EMatchPhase::None]
{T}LogGameMode: Current[EMatchPhase::VersusScreen] Previous[EMatchPhase::CharacterSelect]
{T}LogPMSkinDataManager: UPMSkinDataManagerComponent::DetermineLobbyAnimation SD_AngelicSupport
{T}LogPMSkinDataManager: UPMSkinDataManagerComponent::DetermineLobbyAnimation SD_ChaoticRocketeer
{T}LogPMSkinDataManager: UPMSkinDataManagerComponent::DetermineLobbyAnimation SD_FlexibleBrawler
{T}LogPMSkinDataManager: UPMSkinDataManagerComponent::DetermineLobbyAnimation SD_SpeedySkirmisher
{T}LogPMSkinDataManager: UPMSkinDataManagerComponent::DetermineLobbyAnimation SD_TempoSniper
{T}LogPMSkinDataManager: UPMSkinDataManagerComponent::DetermineLobbyAnimation SD_ManipulatingMastermind
{T}Player 'PlayerAlpha' equipping trainings TD_IncreasedSpeedCrossingMidfield
{T}Player 'PlayerBeta' equipping trainings TD_DistancePower
{T}Player 'PlayerGamma' equipping trainings TD_FasterDashes2
{T}Player 'PlayerDelta' equipping trainings TD_HitSpeed
{T}Player 'PlayerEpsilon' equipping trainings TD_AvoidDamageHitHarder
{T}Player 'PlayerZeta' equipping trainings TD_EnergyCatalyst
"""

PHASE_2 = f"""\
{T}Player 'PlayerAlpha' equipping trainings TD_IncreasedSpeedCrossingMidfield TD_KOKing
{T}Player 'PlayerBeta' equipping trainings TD_DistancePower TD_MultiHitsReduceCooldowns
{T}Player 'PlayerGamma' equipping trainings TD_FasterDashes2 TD_FasterDashes
{T}Player 'PlayerDelta' equipping trainings TD_HitSpeed TD_HitsIncreaseSpeedAndPower
{T}Player 'PlayerEpsilon' equipping trainings TD_AvoidDamageHitHarder TD_BarrierBuff
{T}Player 'PlayerZeta' equipping trainings TD_EnergyCatalyst TD_EnergyDischarge
"""

PHASE_3 = f"""\
{T}Player 'PlayerAlpha' equipping trainings TD_IncreasedSpeedCrossingMidfield TD_KOKing TD_StackingSize
{T}Player 'PlayerBeta' equipping trainings TD_DistancePower TD_MultiHitsReduceCooldowns TD_HitRockCooldown
{T}Player 'PlayerGamma' equipping trainings TD_FasterDashes2 TD_FasterDashes TD_MovementAbilityCharges
{T}Player 'PlayerDelta' equipping trainings TD_HitSpeed TD_HitsIncreaseSpeedAndPower TD_PrimaryAbilityCooldownReduction
{T}Player 'PlayerEpsilon' equipping trainings TD_AvoidDamageHitHarder TD_BarrierBuff TD_BuffAndDebuffDuration
{T}Player 'PlayerZeta' equipping trainings TD_EnergyCatalyst TD_EnergyDischarge TD_EnhancedOrbsSpeed
"""

PHASE_4 = f"""\
{T}Player 'PlayerAlpha' equipping trainings TD_IncreasedSpeedCrossingMidfield TD_KOKing TD_StackingSize TD_StaggerPowerConversion
{T}Player 'PlayerBeta' equipping trainings TD_DistancePower TD_MultiHitsReduceCooldowns TD_HitRockCooldown TD_OrbShare
{T}Player 'PlayerGamma' equipping trainings TD_FasterDashes2 TD_FasterDashes TD_MovementAbilityCharges TD_FasterProjectiles
{T}Player 'PlayerDelta' equipping trainings TD_HitSpeed TD_HitsIncreaseSpeedAndPower TD_PrimaryAbilityCooldownReduction TD_StrikeRockTowardsAllies
{T}Player 'PlayerEpsilon' equipping trainings TD_AvoidDamageHitHarder TD_BarrierBuff TD_BuffAndDebuffDuration TD_CreationSize
{T}Player 'PlayerZeta' equipping trainings TD_EnergyCatalyst TD_EnergyDischarge TD_EnhancedOrbsSpeed TD_EnergyConversion
"""

PHASE_5 = f"""\
{T}Player 'PlayerAlpha' equipping trainings TD_IncreasedSpeedCrossingMidfield TD_KOKing TD_StackingSize TD_StaggerPowerConversion TD_HitAnythingRestoreStagger
{T}Player 'PlayerBeta' equipping trainings TD_DistancePower TD_MultiHitsReduceCooldowns TD_HitRockCooldown TD_OrbShare TD_SizeIncrease
{T}Player 'PlayerGamma' equipping trainings TD_FasterDashes2 TD_FasterDashes TD_MovementAbilityCharges TD_FasterProjectiles TD_BaseStaggerAndRegen
{T}Player 'PlayerDelta' equipping trainings TD_HitSpeed TD_HitsIncreaseSpeedAndPower TD_PrimaryAbilityCooldownReduction TD_StrikeRockTowardsAllies TD_KnockAnythingRecoverStagger
{T}Player 'PlayerEpsilon' equipping trainings TD_AvoidDamageHitHarder TD_BarrierBuff TD_BuffAndDebuffDuration TD_CreationSize TD_IncreasedSpeedWithStagger
{T}Player 'PlayerZeta' equipping trainings TD_EnergyCatalyst TD_EnergyDischarge TD_EnhancedOrbsSpeed TD_EnergyConversion TD_BlessingCooldownRate
"""

PHASES = [
    ("Game start — CharacterSelect + 6 characters + gear", PHASE_1),
    ("Round 1   — starting awakenings (red highlight)",    PHASE_2),
    ("Round 2   — third awakening",                        PHASE_3),
    ("Round 3   — fourth awakening",                       PHASE_4),
    ("Round 4   — fifth awakening (all slots full)",       PHASE_5),
]


def wait_for_flask(timeout: int = 20) -> bool:
    """Poll the overlay endpoint until Flask is ready."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f'http://127.0.0.1:{PORT}', timeout=1)
            return True
        except Exception:
            time.sleep(0.5)
    return False


def append(content: str) -> None:
    with open(LOG_PATH, 'a', encoding='utf-8') as f:
        f.write(content)


# ── Main ─────────────────────────────────────────────────────────────────────

print("=" * 60)
print("  Awakening Overlay — Test Runner")
print("=" * 60)

# Clear the log so main.py starts from position 0
with open(LOG_PATH, 'w', encoding='utf-8') as f:
    f.write('')
print(f"\nTest log cleared: {LOG_PATH}")

# Launch main.py in a new console window (Windows) or background process
print("Starting main.py...")
if sys.platform == 'win32':
    proc = subprocess.Popen(
        ['cmd', '/k', sys.executable, 'main.py'],
        creationflags=subprocess.CREATE_NEW_CONSOLE,
        cwd=os.path.dirname(os.path.abspath(__file__)),
    )
else:
    proc = subprocess.Popen([sys.executable, 'main.py'])

# Wait for Flask to be ready before writing any log data
print(f"Waiting for overlay server on port {PORT}...", end='', flush=True)
if wait_for_flask():
    print(" ready.")
else:
    print("\nFlask did not start in time. Check main.py for errors.")
    proc.terminate()
    sys.exit(1)

print(f"\nOverlay: http://127.0.0.1:{PORT}")
print(f"Phases will run every {ROUND_DELAY}s. Open OBS now.\n")

for i, (label, content) in enumerate(PHASES):
    if i > 0:
        print(f"  Next phase in {ROUND_DELAY}s...")
        time.sleep(ROUND_DELAY)
    append(content)
    print(f"[{time.strftime('%H:%M:%S')}] Phase {i + 1}: {label}")

print("\nTest complete. Press Ctrl+C to stop.")
try:
    proc.wait()
except KeyboardInterrupt:
    proc.terminate()
