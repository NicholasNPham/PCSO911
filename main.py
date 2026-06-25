# STANDARD LIBRARY IMPORTS
import sys
import datetime
import os
import time

# LOCAL IMPORTS
from ftp_conn import connect_to_ftp, change_directory_911_phone_calls, delete_temp_dir
from ftp_operations import build_directory_manifest, process_single_case, handle_match_results
from ftp_outlook_error import send_error_email
from key import USERNAME, PASSWORD, FTP_LINK, ABSOLUTE_PATH, TEMP_DIR, UNC_PATH_TO_H_DRIVE

# SCHEDULED RUN CONSTANTS
SCHEDULE_HOUR = 15 # 3:00 PM
SCHEDULE_MINUTE = 0
SCHEDULE_DAYS = {0, 1, 2, 3, 4} # MONDAY-FRIDAY
SLEEP_INTERVAL_SECONDS = 60

# CLASS
class Tee:
    def __init__(self, file):
        """
        Initializes the Tee instance with a file object and saves the current stdout.

        Args:
            file: An open writable file object to mirror output into.

        Returns:
            None
        """
        self.file = file # the .txt file you open
        self.terminal = sys.stdout # save the REAL console before replacing it

    def write(self, message):
        """
        Writes a message to both the terminal and the log file.

        Args:
            message (str): The string to write.

        Returns:
            None
        """
        self.terminal.write(message) # sends to real console
        self.file.write(message) # sends to .txt file

    def flush(self):
        """
        Flushes both the terminal and file buffers to ensure output is written immediately.

        Returns:
            None
        """
        self.terminal.flush()
        self.file.flush()

# FUNCTION
def is_scheduled_run_time() -> bool:
    """
    Checks whether the current day and time match the scheduled run window.

    Returns:
        bool: True if the current weekday, hour, and minute match the
              scheduled constants, False otherwise.
    """
    now = datetime.datetime.now()
    return (
        now.weekday() in SCHEDULE_DAYS
        and now.hour == SCHEDULE_HOUR
        and now.minute == SCHEDULE_MINUTE
    )

# MAIN LOOP SETUP
def run_pcso911_script() -> None:
    """
    Executes the full PCSO911 workflow: connects to FTP, builds a directory manifest,
    and processes each case by downloading files, uploading to STAC, and managing
    FTP directory state. Logs all output to a timestamped log file.

    Returns:
        None
    """
    case_count_run = 0

    try:
        ftp = connect_to_ftp(USERNAME, PASSWORD, FTP_LINK)
        change_directory_911_phone_calls(ABSOLUTE_PATH, ftp)
        manifest = build_directory_manifest(ftp)

        if os.path.exists(TEMP_DIR):
            delete_temp_dir(TEMP_DIR)

        case_count = len(manifest)
        date_str = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        log_path = os.path.join(UNC_PATH_TO_H_DRIVE, f"log_{date_str}_{case_count}_cases.txt")

        with open(log_path, "w") as log_file:
            original_stdout = sys.stdout
            sys.stdout = Tee(log_file)

            try:
                # MAIN LOOP
                for child_dir_name, child_dir_data in manifest.items():
                    try:
                        print("V^V^V^V^V^V^V^V^V^V^V^V^V^V^V^V^V^V^V^V^V^V^V^V^V^V^V^V^V^V^V^V^V^V")
                        print(child_dir_name)
                        print(f"number of files: {len(child_dir_data['files'])}")
                        print("-vvvvvvvvvvvvvvvvvvvvvvv-")

                        is_match, temp_dir =  process_single_case(ftp, child_dir_name, child_dir_data)
                        case_count_run = handle_match_results(ftp, is_match, temp_dir, child_dir_data, child_dir_name, case_count_run)

                    except Exception as e:
                        failed_error = f"Failed to process '{child_dir_name}': {e}"
                        print(failed_error)
                        send_error_email(failed_error)
                        continue

            finally:
                sys.stdout = original_stdout

    except Exception as e:
        fatal_error = f"Fatal error during setup: {e}"
        print(fatal_error)
        send_error_email(fatal_error)

if __name__ == "__main__":

    # script_last_ran_date = None
    # while True:
    #     if is_scheduled_run_time() and script_last_ran_date != datetime.date.today():
    #         run_pcso911_script()
    #         script_last_ran_date = datetime.date.today()
    #     else:
    #         print(datetime.datetime.now().strftime("%H:%M"))
    #         time.sleep(SLEEP_INTERVAL_SECONDS)

    # TESTING SCRIPT FUNCTION CALL
    run_pcso911_script()