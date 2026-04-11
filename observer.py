from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from collections import OrderedDict
from processor import process_log_entry, return_true_if_should_upload, publish_state
import os
import sys
import time
from dotenv import load_dotenv

class LogObserver:
    def __init__(self, log_file_path, shared_state):
        self.log_file_path = log_file_path
        self.shared_state = shared_state

        self.observer = Observer()



    def start_monitoring(self):
        event_handler = LogHandler(self.log_file_path, self.shared_state)
        self.observer.schedule(event_handler, os.path.dirname(self.log_file_path), recursive=False)
        self.observer.start()
        print("Started monitoring log file.")

        load_dotenv()
        TEST_LOG_FLAG = os.getenv('TEST_LOG_FLAG', 'False').lower() == 'true' # this stores a boolean!

        if (TEST_LOG_FLAG):

            try:
                with open(self.log_file_path, 'a') as log_file:  # 'a' mode opens the file for appending
                    log_file.write('.\n')  # Write the dot and add a newline for readability
            except (IOError, OSError) as e:
                print(f"Warning: could not write trigger line to log file: {e}")


        try:
            # Keep the script running until interrupted
            while True:
                pass
        except KeyboardInterrupt:
            print("Monitoring stopped.")
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
        self.ALL_LOGS_THIS_GAME = []
        self.MOST_RECENTLY_PUBLISHED_TABLE = []
        self.BOOLEAN_CONSIDER_UPLOAD = False
        self.file_size = 0



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
                        # BOOLEAN_CONSIDER_UPLOAD is true if...
                        # the first time CHARACTERS_LIST is 6, the first time IGN_LIST is 6,
                        # and when information about awakenings being equipped comes in.

                        self.BOOLEAN_CONSIDER_UPLOAD = process_log_entry(
                            line,
                            self.CHARACTERS_LIST,
                            self.IGN_LIST,
                            self.DICT_IGN_TO_AWAKENINGS,
                            self.ALL_LOGS_THIS_GAME,
                            self.MOST_RECENTLY_PUBLISHED_TABLE,
                        )

                        if self.BOOLEAN_CONSIDER_UPLOAD:
                            self.BOOLEAN_CONSIDER_UPLOAD = return_true_if_should_upload(
                                self.CHARACTERS_LIST,
                                self.IGN_LIST,
                                self.DICT_IGN_TO_AWAKENINGS,
                                self.ALL_LOGS_THIS_GAME,
                                self.MOST_RECENTLY_PUBLISHED_TABLE,
                            )  # Check again.

                            # If it's still true, we should definitely update the overlay.
                            if self.BOOLEAN_CONSIDER_UPLOAD:
                                #print(self.DICT_IGN_TO_AWAKENINGS)  # Debug print

                                # Update the overlay state
                                new_table = publish_state(
                                    self.shared_state,
                                    self.CHARACTERS_LIST,
                                    self.IGN_LIST,
                                    self.DICT_IGN_TO_AWAKENINGS,
                                    self.ALL_LOGS_THIS_GAME,
                                    self.MOST_RECENTLY_PUBLISHED_TABLE,
                                )
                                if new_table is not None:
                                    self.MOST_RECENTLY_PUBLISHED_TABLE = new_table

                                # Reset BOOLEAN_CONSIDER_UPLOAD after successful upload
                                self.BOOLEAN_CONSIDER_UPLOAD = False

                # Exit the retry loop if everything succeeds
                #print("on_modified executed successfully.")
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
