# STANDARD LIBRARY IMPORTS
import sys
import datetime
import os
import time

# LOCAL IMPORTS
from credential import load_credentials
from exceptions import CaseProblem, ServiceUnreachable, SystemProblem
from ftp_conn import connect_to_ftp, change_directory_911_phone_calls
from ftp_operations import build_directory_manifest, process_single_case, handle_uploaded_case
from ftp_outlook_error import send_error_email
from ftp_to_stac import StacSession
from key import FTP_LINK, ABSOLUTE_PATH, UNC_PATH_TO_H_DRIVE

# SCHEDULED RUN CONSTANTS
SCHEDULE_HOUR = 15 # 3:00 PM
SCHEDULE_MINUTE = 0
SCHEDULE_DAYS = {0, 1, 2, 3, 4} # MONDAY-FRIDAY
SLEEP_INTERVAL_SECONDS = 60
# Kept next to main.py so a restart of the loop knows today's run already
# happened. Holds only a date.
LAST_RUN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "last_run_date.txt")

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

def read_last_run_date() -> datetime.date | None:
    """
    Reads the date of the last scheduled run from LAST_RUN_FILE.

    Returns:
        datetime.date | None: The recorded date, or None if no run has been
                              recorded yet.

    Raises:
        SystemProblem: If the file exists but does not hold a valid date, so
                       the loop refuses to start rather than guess and maybe
                       run twice in one day.
    """
    if not os.path.exists(LAST_RUN_FILE):
        return None
    with open(LAST_RUN_FILE) as last_run_file:
        content = last_run_file.read().strip()
    try:
        return datetime.date.fromisoformat(content)
    except ValueError:
        raise SystemProblem(
            f"{LAST_RUN_FILE} does not hold a date like 2026-01-31. "
            f"Fix or delete it, then start again."
        )

def record_run_date(run_date: datetime.date) -> None:
    """
    Writes the date of a scheduled run to LAST_RUN_FILE.

    Args:
        run_date (datetime.date): The date to record.

    Returns:
        None
    """
    try:
        with open(LAST_RUN_FILE, "w") as last_run_file:
            last_run_file.write(run_date.isoformat())
    except OSError as e:
        # The loop still remembers the date in memory, so only a restart
        # today could run twice. Not worth skipping the run over.
        print(f"Warning: could not record today's run in {LAST_RUN_FILE}: {e}", flush=True)

def next_scheduled_run(last_ran_date: datetime.date | None) -> datetime.datetime:
    """
    Works out when the scheduled loop will next start a run.

    Args:
        last_ran_date (datetime.date | None): The date the loop last ran, or
                                              None if it has not run yet.

    Returns:
        datetime.datetime: The next scheduled weekday at the scheduled time.
    """
    now = datetime.datetime.now()
    candidate = now.replace(hour=SCHEDULE_HOUR, minute=SCHEDULE_MINUTE, second=0, microsecond=0)
    # The run window is the whole scheduled minute, so today still counts
    # until that minute has fully passed.
    while (
        candidate.weekday() not in SCHEDULE_DAYS
        or candidate.date() == last_ran_date
        or candidate + datetime.timedelta(minutes=1) <= now
    ):
        candidate += datetime.timedelta(days=1)
    return candidate

# MAIN LOOP SETUP
def run_pcso911_script(credentials: dict[str, str]) -> None:
    """
    Executes the full PCSO911 workflow: connects to FTP, builds a directory manifest,
    and processes each case by downloading files, uploading to STAC, and managing
    FTP directory state. Logs all output to a timestamped log file.

    Args:
        credentials (dict[str, str]): Secrets from load_credentials, keyed as in
                                      credential.CREDENTIALS.

    Returns:
        None
    """
    case_count_run = 0

    try:
        ftp = connect_to_ftp(credentials["ftp_username"], credentials["ftp_password"], FTP_LINK)
        change_directory_911_phone_calls(ABSOLUTE_PATH, ftp)
        manifest = build_directory_manifest(ftp)

        case_count = len(manifest)
        date_str = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        log_path = os.path.join(UNC_PATH_TO_H_DRIVE, f"log_{date_str}_{case_count}_cases.txt")

        with open(log_path, "w") as log_file:
            original_stdout = sys.stdout
            sys.stdout = Tee(log_file)

            try:
                # One browser for the whole run. It signs in on the first case
                # and closes when the loop ends, however it ends.
                with StacSession(credentials["stac_username"], credentials["stac_password"]) as stac:
                    # MAIN LOOP
                    for child_dir_name, child_dir_data in manifest.items():
                        try:
                            print("V^V^V^V^V^V^V^V^V^V^V^V^V^V^V^V^V^V^V^V^V^V^V^V^V^V^V^V^V^V^V^V^V^V")
                            print(child_dir_name)
                            print(f"number of files: {len(child_dir_data['files'])}")
                            print("-vvvvvvvvvvvvvvvvvvvvvvv-")

                            process_single_case(ftp, stac, child_dir_name, child_dir_data)
                            case_count_run = handle_uploaded_case(ftp, child_dir_data, child_dir_name, case_count_run)

                        except CaseProblem as e:
                            # Not found, name mismatch, or Save unconfirmed:
                            # a person looks at this one, the run goes on.
                            review_error = f"Manual review needed for '{child_dir_name}': {e}"
                            print(review_error)
                            send_error_email(review_error)
                            continue

                        except ServiceUnreachable as e:
                            # Before SystemProblem, which it belongs to. STAC
                            # not answering is an outage, not a PCSO911 bug, so
                            # the email says to wait rather than to go debugging.
                            unreachable_error = (
                                f"Run stopped at '{child_dir_name}': STAC did not respond in time, "
                                f"even after a retry in a fresh browser. Nothing is wrong with PCSO911; "
                                f"run it again once STAC is back. The remaining cases are still on FTP. ({e})"
                            )
                            print(unreachable_error)
                            send_error_email(unreachable_error)
                            break

                        except SystemProblem as e:
                            # STAC still broken after a retry in a fresh browser.
                            # Every later case would fail the same way, so stop
                            # with one email instead of one per remaining case.
                            stopped_error = f"Run stopped at '{child_dir_name}': {e}"
                            print(stopped_error)
                            send_error_email(stopped_error)
                            break

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

    # Loaded once, before the menu, so a missing secret fails while someone
    # is at the console instead of at 3:00 PM inside the scheduled loop.
    try:
        loaded_credentials = load_credentials()
    except SystemProblem as credential_error:
        print(credential_error)
        sys.exit(1)

    print("1. Run While Loop")
    print("2. Run 1 Loop")
    option = input("enter option: ")

    if option == "1":
        try:
            script_last_ran_date = read_last_run_date()
        except SystemProblem as last_run_error:
            print(last_run_error)
            sys.exit(1)

        if script_last_ran_date == datetime.date.today():
            print("Already ran today. Not running again until the next scheduled day.", flush=True)
        elif script_last_ran_date is not None:
            print(f"Last scheduled run: {script_last_ran_date:%A %Y-%m-%d}", flush=True)
        else:
            print("No scheduled run recorded yet.", flush=True)

        while True:
            if is_scheduled_run_time() and script_last_ran_date != datetime.date.today():
                print(f"Starting scheduled run at {datetime.datetime.now():%Y-%m-%d %I:%M %p}", flush=True)
                # Recorded before the run, so a restart after a hang or crash
                # today does not start a second run.
                script_last_ran_date = datetime.date.today()
                record_run_date(script_last_ran_date)
                run_pcso911_script(loaded_credentials)
                print(
                    f"Run finished at {datetime.datetime.now():%Y-%m-%d %I:%M %p}. "
                    f"Still running. Next run: {next_scheduled_run(script_last_ran_date):%A %Y-%m-%d at %I:%M %p}",
                    flush=True,
                )
            else:
                print(
                    f"{datetime.datetime.now():%H:%M} waiting for the "
                    f"{next_scheduled_run(script_last_ran_date):%I:%M %p run on %A %Y-%m-%d}",
                    flush=True,
                )
                time.sleep(SLEEP_INTERVAL_SECONDS)
    elif option == "2":
        run_pcso911_script(loaded_credentials)
