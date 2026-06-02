# Standard Library Imports
import ftplib
from ftplib import FTP
import re
import os
import shutil
import sys
import datetime
import time
import random
import string

# Local Imports
from key import USERNAME, PASSWORD, FTP_LINK, ABSOLUTE_PATH, UNIVERSAL_CASE_NUMBER_PATTERN, UNC_PATH_TO_H_DRIVE, TEMP_DIR
from ftp_to_stac import run_stac_script
from ftp_outlook_error import send_error_email

# CONSTANTS
COMPLETED_DIR_NAME = "__Completed"
HAS_HTM_KEY = "has_htm"
FTP_TYPE_DIR = "dir"
FTP_TYPE_FILE = "file"
ERROR_HTM_PREFIX = '_ERROR_HTM '
DELETE_DIR_PREFIX = '_DELETE '
SCRIPT_RAN_SUFFIX = ' _SCRIPT '
EMPTY_FILE_SIZE = 0
CURRENT_WORKING_DIRECTORY = '.'
RETURN_TO_PARENT_DIRECTORY = '..'
FILE_METADATA_TYPE = "type"
HTM_EXTENSION = ".htm"
HTML_EXTENSION = ".html"
MP3_EXTENSION = ".mp3"
PDF_EXTENSION = ".pdf"
WAV_EXTENSION = ".wav"
FTP_PATH_SEPARATOR = "/"
FTP_RETR_COMMAND = "RETR"
ALLOWED_EXTENSIONS = {MP3_EXTENSION, PDF_EXTENSION, WAV_EXTENSION}
HTM_EXTENSIONS = {HTM_EXTENSION, HTML_EXTENSION}

# SCHEDULED RUN CONSTANTS
SCHEDULE_HOUR = 15 # 3:00 PM
SCHEDULE_MINUTE = 0
SCHEDULE_DAYS = {0, 1, 2, 3, 4} # MONDAY-FRIDAY
SLEEP_INTERVAL_SECONDS = 60

# UCN CONSTANTS
UCN_SEPARATOR = "-"
UCN_UNKNOWN_GROUP = "0000"
UCN_CASE_TYPE = "CJ"
UCN_CASE_TYPE_INDEX = 2
UCN_SEQUENCE_GROUP_INDEX = -2
UCN_UNKNOWN_REPLACEMENT = "A000"
UCN_TRIM_LENGTH = -3

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

# FUNCTIONS
def connect_to_ftp(username: str, password: str, ftp_link: str) -> FTP:
    """
    Connect to FTP server.

    Args:
        username: FTP account username.
        password: FTP account password.
        ftp_link: FTP server address.

    Returns:
        FTP connection object or quits if login fails.
    """
    ftp = FTP(ftp_link)

    try:
        ftp.login(username, password)
        print("Login Successful")
        return ftp
    except ftplib.error_perm as LOGIN_ERROR:
        ftp.quit()
        raise ConnectionError(f"Login Failed: {LOGIN_ERROR}")

def change_directory_911_phone_calls(absolute_path: str, ftp: FTP) -> FTP:
    """
    changing directory to PCSO911

    Args:
        absolute_path: absolute path to directory to change
        ftp: FTP connection object
    Returns:
        ftp connection object or None if change fails.
    """
    try:
        ftp.cwd(absolute_path)
        print("Changed Directory to PCSO911")
        return ftp
    except ftplib.error_perm as CHANGE_DIRECTORY_ERROR:
        ftp.quit()
        raise ConnectionError(f"Failed to Change Directory: {CHANGE_DIRECTORY_ERROR}")

def reformat_unknown_ucn(ucn: str) -> str:
    """
    Reformats a UCN where the second-to-last group is '0000' by replacing
    the first zero with 'A', indicating an unknown case number.

    Args:
        ucn (str): Universal Case Number string.

    Returns:
        str: Reformatted UCN with 'A000' in the second-to-last group if the
             condition is met, otherwise returns the original UCN unchanged.
    """
    ucn_in_group = ucn.split(UCN_SEPARATOR)
    if ucn_in_group[UCN_SEQUENCE_GROUP_INDEX] == UCN_UNKNOWN_GROUP and ucn_in_group[UCN_CASE_TYPE_INDEX] == UCN_CASE_TYPE:
        ucn_in_group[UCN_SEQUENCE_GROUP_INDEX] = UCN_UNKNOWN_REPLACEMENT
        reformatted_ucn = UCN_SEPARATOR.join(ucn_in_group)
        return reformatted_ucn[:UCN_TRIM_LENGTH]
    return ucn

def is_valid_file_size(filename: str, ftp: FTP) -> bool:
    """
    checks to see if the file has a size that's bigger than 0 megabytes

    Args:
        filename: filename to check
        ftp: FTP connection object
    Returns:
        True or False (Boolean)
    """
    try:
        if ftp.size(filename) > EMPTY_FILE_SIZE:
            return True
        else:
            print(f"File '{filename}' is 0 bytes. Skipping.")
            print("-------------------")
            return False
    except ftplib.error_perm as NO_MEGABYTES_ERROR:
        print(f"Failed to get size of file: {NO_MEGABYTES_ERROR}")
        return False

def random_six_digit_suffix() -> str:
    """
    Generates a random six-digit numeric string to append to renamed directories,
    preventing name collisions on the FTP server.

    Returns:
        str: A six-character string composed of random digits (0-9).
    """
    random_digits = "".join(random.choices(string.digits, k=6))
    return random_digits

def rename_directory(ftp: FTP, old_name: str, prefix: str, suffix: str, digits: str) -> str:
    """
    Renames a directory by prepending a prefix, appending a suffix, and appending a random digit string to its current name.

    Args:
        ftp: FTP connection object
        old_name: current directory name
        prefix: prefix string to prepend to the directory name
        suffix: suffix string to append to the directory name
        digits (str): Six-digit random numeric string appended after the suffix to prevent name collisions.
    Returns:
        str: New directory name.
    Raises:
        Exception: If the FTP rename operation fails.
    """
    try:
        new_name = prefix + old_name + suffix + digits
        ftp.rename(old_name, new_name)
        print(f"Renamed '{old_name}' to '{new_name}'")
        print("-------------------")
        return new_name
    except ftplib.error_perm as FAILED_RENAME_ERROR:
        print(f"Failed to rename '{old_name}': {FAILED_RENAME_ERROR}")
        print("-------------------")
        raise Exception(f"Failed to rename '{old_name}': {FAILED_RENAME_ERROR}")

def should_skip_directory(child_directory_name: str) -> bool:
    """
    Determines whether a child directory should be skipped during processing.

    Args:
        child_directory_name (str): Name of the child directory to check.

    Returns:
        bool: True if the directory should be skipped, False otherwise.
    """
    if child_directory_name == COMPLETED_DIR_NAME:
        return True
    if child_directory_name.startswith(DELETE_DIR_PREFIX):
        return True
    if child_directory_name.startswith(ERROR_HTM_PREFIX):
        return True
    return False

def move_to_completed(ftp: FTP, dir_name: str, completed_folder: str) -> None:
    """
    Moves a directory into the completed folder.

    Args:
        ftp: FTP connection object
        dir_name: current directory name
        completed_folder: name of the completed folder to move into
    Returns:
        None
    """
    try:
        ftp.rename(dir_name, f"{completed_folder}{FTP_PATH_SEPARATOR}{dir_name}")
        print(f"Moved '{dir_name}' to '{completed_folder}{FTP_PATH_SEPARATOR}{dir_name}'")
        print("-------------------")
    except ftplib.all_errors as MOVE_ERROR:
        print(f"Failed to move '{dir_name}' : {MOVE_ERROR}")
        send_error_email(f"Failed to move '{dir_name}' : {MOVE_ERROR}")
        print("-------------------")

def download_files_to_temp(ftp: FTP, file_list: list) -> tuple:
    """
        Downloads a list of files to a temp folder.

    Args:
        ftp: FTP connection object
        file_list: list of filenames to download
    Returns:
        tuple:
            - TEMP_DIR: path to the temp directory
            - local_file_path: list of local file paths
    """
    os.makedirs(TEMP_DIR, exist_ok=True)
    local_file_path = []

    try:
        for filename in file_list:
            local_path = os.path.join(TEMP_DIR, filename)
            with open(local_path, "wb") as file:
                ftp.retrbinary(f"{FTP_RETR_COMMAND} {filename}", file.write)
            local_file_path.append(local_path)
            print(f"Downloaded {filename} to {local_path}")
    except (ftplib.all_errors, OSError) as DOWNLOAD_ERROR:
        send_error_email(f"Failed to download files to Network Drive: {DOWNLOAD_ERROR}")
        raise
    print("-------------------")

    return TEMP_DIR, local_file_path

def delete_temp_dir(temp_dir: str) -> None:
    """
    Deletes the temporary directory and all of its contents.

    Args:
        temp_dir (str): Absolute path to the temporary directory to delete.

    Returns:
        None
    """
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
        print(f"Deleted temp directory: {temp_dir}")
        print("-------------------")

def extract_ucn_from_child_dir_name(child_dir_name: str) -> str | None:
    """
    Extracts a Universal Case Number (UCN) from a child directory name.

    Args:
        child_dir_name: Name of the child directory to search for a UCN.

    Returns:
        UCN string if found, otherwise None.
    """

    universal_case_number = re.search(UNIVERSAL_CASE_NUMBER_PATTERN, child_dir_name, re.IGNORECASE)

    if universal_case_number:
        return universal_case_number.group()
    else:
        return None

def list_processable_directories(ftp: FTP) -> list:
    """
    Returns a list of directory names in the current FTP location
    that are eligible for processing.

    Args:
        ftp: FTP connection object

    Returns:
        list[str]: Directory names that are not skipped.
    """

    processable_directories = []

    for child_directory_name, attribute in ftp.mlsd(CURRENT_WORKING_DIRECTORY):
        if should_skip_directory(child_directory_name):
            continue
        elif attribute.get(FILE_METADATA_TYPE) == FTP_TYPE_DIR:
            processable_directories.append(child_directory_name)

    return processable_directories

def collect_directory_contents(ftp: FTP, dir_name: str) -> dict:
    """
    Collects the contents of a single FTP directory.
    CDs into the directory, checks for HTM files, collects valid
    .mp3 and .pdf filenames, then CDs back out.

    Args:
        ftp: FTP connection object
        dir_name (str): Name of the directory to inspect.

    Returns:
        dict: {
            "files": list[str] - valid .mp3 and .pdf filenames,
            "has_htm": bool - True if any .htm or .html file was found
        }
    """
    try:
        ftp.cwd(dir_name)

        has_htm = False
        files = []

        for filename, attributes in ftp.mlsd(CURRENT_WORKING_DIRECTORY):
            if attributes.get(FILE_METADATA_TYPE) != FTP_TYPE_FILE:
                continue

            ext = os.path.splitext(filename.lower())[1]

            if ext in HTM_EXTENSIONS:
                print(f"HTM/HTML file detected: '{filename}'")
                has_htm = True

            elif ext in ALLOWED_EXTENSIONS:
                if is_valid_file_size(filename, ftp):
                    files.append(filename)

            else:
                print(f"Unexpected file extension skipped: '{filename}' in '{dir_name}'")

    except (ftplib.all_errors, OSError) as CHANGE_DIR_IN_ERROR:
        send_error_email(f"Failed to cwd into {dir_name}: {CHANGE_DIR_IN_ERROR}")
        print(f"Failed to cwd into {dir_name}: {CHANGE_DIR_IN_ERROR}")
        raise

    try:
        ftp.cwd(RETURN_TO_PARENT_DIRECTORY)
    except (ftplib.all_errors, OSError)as CHANGE_DIR_OUT_ERROR:
        send_error_email(f"Failed to cwd out of {dir_name}: {CHANGE_DIR_OUT_ERROR}")
        print(f"Failed to cwd out {dir_name}: {CHANGE_DIR_OUT_ERROR}")
        raise


    return {"files": files, "has_htm": has_htm}

def build_directory_manifest(ftp: FTP) -> dict:
    """
    Builds a manifest of all processable directories and their contents.
    Orchestrates list_processable_directories and collect_directory_contents,
    extracts UCNs, and skips directories with no valid files or no UCN.

    Args:
        ftp: FTP connection object

    Returns:
        dict: {
            dir_name (str): {
                "ucn"     (str):       Universal Case Number extracted from dir name,
                "has_htm" (bool):      True if directory contains an .htm or .html file,
                "files"   (list[str]): Valid non-HTM filenames inside the directory
            }
        }
    """

    manifest = {}

    processable_directories_list = list_processable_directories(ftp)

    for child_directory in processable_directories_list:
        contents = collect_directory_contents(ftp, child_directory)

        if not contents["files"]:
            print(f"Warning: No valid files found in '{child_directory}'. Skipping.")
            continue

        ucn = extract_ucn_from_child_dir_name(child_directory)
        if ucn is None:
            print(f"Warning: No UCN found in directory name '{child_directory}'. Skipping.")
            continue

        manifest[child_directory] = {
            "ucn": ucn,
            "has_htm": contents["has_htm"],  # pull from contents
            "files": contents["files"],  # pull from contents
        }

    # Uncomment to debug manifest contents
    # print("-------------------------")
    # print(manifest)
    # print("-------------------------")

    return manifest

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

def process_single_case(ftp: FTP, child_dir_name: str, child_dir_data: dict) -> tuple:
    """
    Downloads files for a single case, reformats the UCN, and runs the STAC upload script.

    Args:
        ftp (FTP): Active FTP connection object.
        child_dir_name (str): Name of the child directory on the FTP server.
        child_dir_data (dict): Manifest entry containing 'ucn', 'files', and 'has_htm' keys.

    Returns:
        tuple: (is_match (bool), temp_dir (str)) — whether STAC found a match and the
               path to the local temp directory containing downloaded files.
    """
    ftp.cwd(child_dir_name)
    temp_dir, local_file_paths = download_files_to_temp(ftp, child_dir_data["files"])
    ftp.cwd(RETURN_TO_PARENT_DIRECTORY)

    ucn = child_dir_data["ucn"]
    reformatted = reformat_unknown_ucn(ucn)
    print(f"Original UCN: {ucn}")
    print(f"Reformatted UCN: {reformatted}")

    is_match = run_stac_script(reformatted, local_file_paths, child_dir_name)

    return is_match, temp_dir

def handle_match_results(ftp: FTP, is_match: bool, temp_dir: str, child_dir_data: dict, child_dir_name: str, case_count_run: int) -> int:
    """
    Handles post-STAC cleanup and FTP directory management based on match result.

    If matched: deletes temp files, renames and moves the directory to Completed,
    or flags it with an HTM error prefix if an HTM file was detected.
    If not matched: deletes temp files and sends a no-match error notification.

    Args:
        ftp (FTP): Active FTP connection object.
        is_match (bool): Whether STAC found a matching case.
        temp_dir (str): Path to the local temp directory to delete.
        child_dir_data (dict): Manifest entry containing 'has_htm' key.
        child_dir_name (str): Name of the child directory on the FTP server.
        case_count_run (int): Running count of successfully completed cases.

    Returns:
        int: Updated case count.
    """
    if is_match:
        delete_temp_dir(temp_dir)
        if child_dir_data[HAS_HTM_KEY]:
            renamed = rename_directory(ftp, child_dir_name, ERROR_HTM_PREFIX, SCRIPT_RAN_SUFFIX, random_six_digit_suffix())
            htm_file_error = f"HTM file detected — renamed to '{renamed}', skipping move to Completed."
            print(htm_file_error)
            send_error_email(htm_file_error)
        else:
            renamed = rename_directory(ftp, child_dir_name, DELETE_DIR_PREFIX, SCRIPT_RAN_SUFFIX, random_six_digit_suffix())
            move_to_completed(ftp, renamed, COMPLETED_DIR_NAME)
            case_count_run += 1
            print(f"Case count: {case_count_run}")
    else:
        delete_temp_dir(temp_dir)
        no_matching_stac_ucn_error = f"No match found for '{child_dir_name}'. Directory left on FTP."
        print(no_matching_stac_ucn_error)
        send_error_email(no_matching_stac_ucn_error)

    return case_count_run

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

    script_last_ran_date = None
    while True:
        if is_scheduled_run_time() and script_last_ran_date != datetime.date.today():
            run_pcso911_script()
            script_last_ran_date = datetime.date.today()
        else:
            print(datetime.datetime.now().strftime("%H:%M"))
            time.sleep(SLEEP_INTERVAL_SECONDS)

    # TESTING SCRIPT FUNCTION CALL
    # run_pcso911_script()
