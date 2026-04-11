from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from collections import OrderedDict
from processor import process_log_entry, return_true_if_should_upload, publish_state
import re
import os
import sys
import time
from dotenv import load_dotenv


def _find_latest_game_start(lines):
    """
    Return the index of the last line containing 'Current[EMatchPhase::PreGame]'.
    Falls back to 0 (start of file) if no such line exists.
    """
    marker = "Current[EMatchPhase::PreGame]"
    start_index = 0
    for i, line in enumerate(lines):
        cleaned = re.sub(r'^\[.*?\]\[.*?\]', '', line).strip()
        if marker in cleaned:
            start_index = i
    return start_index

class LogObserver:
    def __init__(self, log_file_path, shared_state):
        self.log_file_path = log_file_path
        self.shared_state = shared_state

        self.observer = Observer()
        # Handler created here so it can be accessed for rescan before the thread starts
        self.handler = LogHandler(self.log_file_path, self.shared_state)

    def rescan(self):
        """Reset all state and re-read the entire log from the beginning."""
        self.handler.rescan()

    def start_monitoring(self):
        self.observer.schedule(self.handler, os.path.dirname(self.log_file_path), recursive=False)
        self.observer.start()
        print("Started monitoring log file.")

        # Do an initial scan from the latest game so we don't carry over old game data.
        # This also advances file_size so on_modified only reads new lines going forward.
        self.handler.rescan()

        load_dotenv()
        TEST_LOG_FLAG = os.getenv('TEST_LOG_FLAG', 'False').lower() == 'true' # this stores a boolean!

        if (TEST_LOG_FLAG):

            try:
                with open(self.log_file_path, 'a') as log_file:  # 'a' mode opens the file for appending
                    log_file.write('.\n')  # Write the dot and add a newline for readability
            except (IOError, OSError) as e:
                print(f"Warning: could not write trigger line to log file: {e}")


        try:
            while self.observer.is_alive():
                self.observer.join(timeout=1)
        except KeyboardInterrupt:
            self.observer.stop()
        finally:
            self.observer.join()

class LogHandler(FileSystemEventHandler):

    def __init__(self, log_file_path, shared_state):
        self.log_file_path = log_file_path
        self.shared_state = shared_state

        self.CHARACTERS_LIST = []
        self.IGN_LIST = []
        self.DICT_IGN_TO_AWAKENINGS = OrderedDict() # initializes an empty ordered dict.
        self.DICT_IGN_TO_CHARACTER = {}
        self.DICT_IGN_TO_TEAM = {}
        self.ALL_LOGS_THIS_GAME = []
        self.MOST_RECENTLY_PUBLISHED_TABLE = []
        self.BOOLEAN_CONSIDER_UPLOAD = False
        self.file_size = 0

    def _process_line(self, line):
        """Process a single log line and handle the result. Returns True if published."""
        result = process_log_entry(
            line,
            self.CHARACTERS_LIST,
            self.IGN_LIST,
            self.DICT_IGN_TO_AWAKENINGS,
            self.DICT_IGN_TO_CHARACTER,
            self.DICT_IGN_TO_TEAM,
            self.ALL_LOGS_THIS_GAME,
            self.MOST_RECENTLY_PUBLISHED_TABLE,
        )

        if result == "CLEAR":
            self.shared_state.clear()
            self.BOOLEAN_CONSIDER_UPLOAD = False
            return False

        self.BOOLEAN_CONSIDER_UPLOAD = bool(result) if result else False

        if self.BOOLEAN_CONSIDER_UPLOAD:
            self.BOOLEAN_CONSIDER_UPLOAD = return_true_if_should_upload(
                self.CHARACTERS_LIST,
                self.IGN_LIST,
                self.DICT_IGN_TO_AWAKENINGS,
                self.DICT_IGN_TO_CHARACTER,
                self.ALL_LOGS_THIS_GAME,
                self.MOST_RECENTLY_PUBLISHED_TABLE,
            )

            if self.BOOLEAN_CONSIDER_UPLOAD:
                new_table = publish_state(
                    self.shared_state,
                    self.CHARACTERS_LIST,
                    self.IGN_LIST,
                    self.DICT_IGN_TO_AWAKENINGS,
                    self.DICT_IGN_TO_CHARACTER,
                    self.DICT_IGN_TO_TEAM,
                    self.ALL_LOGS_THIS_GAME,
                    self.MOST_RECENTLY_PUBLISHED_TABLE,
                )
                if new_table is not None:
                    self.MOST_RECENTLY_PUBLISHED_TABLE = new_table

                self.BOOLEAN_CONSIDER_UPLOAD = False
                return True

        return False

    def rescan(self):
        """Clear all state and re-read the log file, starting from the latest game."""
        print("Rescan requested — clearing state and re-reading log from latest game.")
        self.CHARACTERS_LIST.clear()
        self.IGN_LIST.clear()
        self.DICT_IGN_TO_AWAKENINGS.clear()
        self.DICT_IGN_TO_CHARACTER.clear()
        self.DICT_IGN_TO_TEAM.clear()
        self.ALL_LOGS_THIS_GAME.clear()
        self.MOST_RECENTLY_PUBLISHED_TABLE = []
        self.BOOLEAN_CONSIDER_UPLOAD = False
        self.file_size = 0
        self.shared_state.clear()

        retry_count = 0
        max_retries = 8
        while retry_count < max_retries:
            try:
                current_size = os.path.getsize(self.log_file_path)
                with open(self.log_file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                # Always advance file_size to the current end so on_modified
                # only picks up new lines written after this rescan.
                self.file_size = current_size

                lines = content.splitlines()
                start_index = _find_latest_game_start(lines)
                print(f"Rescan: starting from line {start_index} (latest EMatchPhase::PreGame).")
                for line in lines[start_index:]:
                    self._process_line(line)
                print("Rescan complete.")
                break
            except Exception as e:
                retry_count += 1
                print(f"Error during rescan (attempt {retry_count}): {e}")
                if retry_count < max_retries:
                    time.sleep(1)
                else:
                    print("Rescan failed after max retries.")

    def on_modified(self, event):
        retry_count = 0
        max_retries = 8

        while retry_count < max_retries:
            try:
                # Check if the event is not a directory and matches the log file path
                if not event.is_directory and event.src_path == self.log_file_path:
                    current_size = os.path.getsize(self.log_file_path)

                    # Read new content from the log file
                    with open(self.log_file_path, "r", encoding="utf-8") as file:
                        file.seek(self.file_size)
                        new_content = file.read()

                    self.file_size = current_size
                    log_lines = new_content.splitlines()

                    for line in log_lines:
                        self._process_line(line)

                # Exit the retry loop if everything succeeds
                break

            except Exception as e:
                retry_count += 1
                print(f"Error in on_modified function (attempt {retry_count}): {e}")

                # Wait before retrying (optional: exponential backoff)
                if retry_count < max_retries:
                    wait_time = 1  # Adjust wait time as needed
                    print(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    print("Max retries reached. Operation failed.")
                    raise  # Re-raise the exception if max retries are reached
