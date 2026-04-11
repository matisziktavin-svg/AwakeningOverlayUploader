import os
import sys
import queue
import threading
import tkinter as tk
import pygetwindow
from dotenv import load_dotenv

from observer import LogObserver
from overlay_server import SharedState, start_flask_server
from gui import StatusWindow

#pyinstaller --noconfirm AwakeningOverlayUploader.spec


def is_omega_strikers_window_open():
    game_title = "OmegaStrikers"
    windows = pygetwindow.getAllWindows()
    for window in windows:
        if game_title in window.title:
            return True
    return False

def loadfromenv():
    load_dotenv()

    TEST_LOG_FLAG = os.getenv('TEST_LOG_FLAG', 'False').lower() == 'true'
    OVERLAY_PORT = int(os.getenv('OVERLAY_PORT', '5000'))

    if TEST_LOG_FLAG is True:
        TEST_LOG_FILEPATH = os.getenv('TEST_LOG_FILEPATH')
    else:
        TEST_LOG_FILEPATH = os.path.join(os.getenv('LOCALAPPDATA'), 'OmegaStrikers', 'Saved', 'Logs', 'OmegaStrikers.log')

    return TEST_LOG_FLAG, TEST_LOG_FILEPATH, OVERLAY_PORT

def main():
    # Required for console=False PyInstaller builds — print() would crash otherwise
    if sys.stdout is None:
        sys.stdout = open(os.devnull, 'w')
    if sys.stderr is None:
        sys.stderr = open(os.devnull, 'w')

    TEST_LOG_FLAG, TEST_LOG_FILEPATH, OVERLAY_PORT = loadfromenv()

    overlay_url = f"http://127.0.0.1:{OVERLAY_PORT}/"
    status_queue = queue.Queue()
    root = tk.Tk()

    if not TEST_LOG_FLAG and not is_omega_strikers_window_open():
        status_queue.put("Omega Strikers not detected. Closing in 10s...")
        window = StatusWindow(root, status_queue, overlay_url)
        root.after(10_000, root.destroy)
        window.run()
        os._exit(0)

    shared_state = SharedState()
    start_flask_server(shared_state, OVERLAY_PORT)

    status_queue.put("Monitoring log file...")
    log_observer = LogObserver(TEST_LOG_FILEPATH, shared_state)
    threading.Thread(target=log_observer.start_monitoring, daemon=True, name="MonitoringThread").start()

    status_queue.put("Active — add URL to OBS Browser Source")
    window = StatusWindow(root, status_queue, overlay_url, refresh_callback=log_observer.rescan)
    window.run()

if __name__ == "__main__":
    main()
