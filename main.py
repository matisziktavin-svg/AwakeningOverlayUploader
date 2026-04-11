from watchdog.observers import Observer
from observer import LogObserver
from overlay_server import SharedState, start_flask_server
import os
import sys
import time
import pygetwindow
from dotenv import load_dotenv

#pyinstaller --noconfirm AwakeningOverlayUploader.spec


def is_omega_strikers_window_open():
    game_title = "OmegaStrikers"
    windows = pygetwindow.getAllWindows()
    for window in windows:
        if game_title in window.title:
            return True
    print("Omega strikers is not running. closing app.")
    return False

def loadfromenv():
    load_dotenv()

    TEST_LOG_FLAG = os.getenv('TEST_LOG_FLAG', 'False').lower() == 'true'  # stores a boolean
    OVERLAY_PORT = int(os.getenv('OVERLAY_PORT', '5000'))

    if TEST_LOG_FLAG is True:
        TEST_LOG_FILEPATH = os.getenv('TEST_LOG_FILEPATH')
    else:
        TEST_LOG_FILEPATH = os.path.join(os.getenv('LOCALAPPDATA'), 'OmegaStrikers', 'Saved', 'Logs', 'OmegaStrikers.log')

    return TEST_LOG_FLAG, TEST_LOG_FILEPATH, OVERLAY_PORT

def main():
    TEST_LOG_FLAG, TEST_LOG_FILEPATH, OVERLAY_PORT = loadfromenv()

    if TEST_LOG_FLAG is False:
        if is_omega_strikers_window_open() is False:
            print('Omega Strikers is not open. Exiting App in 10 seconds.')
            time.sleep(10)
            os._exit(0)

    shared_state = SharedState()
    start_flask_server(shared_state, OVERLAY_PORT)

    log_observer = LogObserver(TEST_LOG_FILEPATH, shared_state)
    log_observer.start_monitoring()

if __name__ == "__main__":
    main()
