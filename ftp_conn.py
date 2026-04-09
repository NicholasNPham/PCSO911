# Standard Library Imports
import ftplib
from ftplib import FTP
import re
import os
import shutil

# Local Imports
from key import USERNAME, PASSWORD, FTP_LINK, ABSOLUTE_PATH, UNIVERSAL_CASE_NUMBER_PATTERN
from ftp_to_stac import run_stac_script

# CONSTANTS
COMPLETED_DIR_NAME = "__Completed"
HAS_HTM_KEY = "has_htm"
FTP_TYPE_DIR = "dir"
FTP_TYPE_FILE = "file"
ERROR_HTM_PREFIX = '_ERROR_HTM '
DELETE_DIR_PREFIX = '_DELETE '
TEMP_DIR =  r"H:\911_TEMP_FILES"
EMPTY_FILE_SIZE = 0
CURRENT_WORKING_DIRECTORY = '.'
RETURN_TO_PARENT_DIRECTORY = '..'
FILE_METADATA_TYPE = "type"
HTM_EXTENSION = ".htm"
HTML_EXTENSION = ".html"

# UCN CONSTANTS
UCN_SEPARATOR = "-"
UCN_UNKNOWN_GROUP = "0000"
UCN_CASE_TYPE = "CJ"
UCN_CASE_TYPE_INDEX = 2
UCN_SEQUENCE_GROUP_INDEX = -2
UCN_UNKNOWN_REPLACEMENT = "A000"
UCN_TRIM_LENGTH = -3

# FUNCTIONS
def connect_to_ftp(username, password, ftp_link):
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

def change_directory_911_phone_calls(absolute_path, ftp):
    """
    changing directory to PSCO911

    Args:
        absolute_path: absolute path to directory to change
        ftp: FTP connection object
    Returns:
        ftp connection object or None if change fails.
    """
    try:
        ftp.cwd(absolute_path)
        print("Changed Directory to PSCO911")
        return ftp
    except ftplib.error_perm as CHANGE_DIRECTORY_ERROR:
        ftp.quit()
        raise ConnectionError(f"Failed to Change Directory: {CHANGE_DIRECTORY_ERROR}")

def reformat_unknown_ucn(ucn):
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

def is_valid_file(filename, ftp):
    """
    checks to see if the file has a size thats bigger than 0 megabytes

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

def rename_directory(ftp, old_name, prefix):
    """
    Renames a directory by adding a prefix to its current name.

    Args:
        ftp: FTP connection object
        old_name: current directory name
        prefix: prefix string to prepend to the directory name
    Returns:
        str: New directory name.
    Raises:
        Exception: If the FTP rename operation fails.
    """
    try:
        new_name = prefix + old_name
        ftp.rename(old_name, new_name)
        print(f"Renamed '{old_name}' to '{new_name}'")
        print("-------------------")
        return new_name
    except ftplib.error_perm as FAILED_RENAME_ERROR:
        print(f"Failed to rename '{old_name}': {FAILED_RENAME_ERROR}")
        print("-------------------")
        raise Exception(f"Failed to rename '{old_name}': {FAILED_RENAME_ERROR}")

def dir_contains_htm_file(ftp):
    """
    Scans the current FTP directory for any .htm or .html files.

    Args:
        ftp: FTP connection object (already cd'd into the child directory)

    Returns:
        bool: True if any .htm or .html file is found, False otherwise.
    """
    for filename, attributes in ftp.mlsd(CURRENT_WORKING_DIRECTORY):
        if attributes.get(FILE_METADATA_TYPE) == FTP_TYPE_FILE:
            if filename.lower().endswith((HTM_EXTENSION, HTML_EXTENSION)):
                print(f"HTM/HTML file detected: '{filename}'")
                return True
    return False

def should_skip_directory(child_directory_name):
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

def move_to_completed(ftp, dir_name, completed_folder):
    """
    Moves a directory into the completed folder.

    Args:
        ftp: FTP connection object
        dir_name: current directory name
        completed_folder: name of the completed folder to move into
    """
    try:
        ftp.rename(dir_name, f"{completed_folder}/{dir_name}")
        print(f"Moved '{dir_name}' to '{completed_folder}/{dir_name}'")
    except ftplib.error_perm as MOVE_ERROR:
        print(f"Failed to move '{dir_name}' : {MOVE_ERROR}")
        print("-------------------")

def download_files_to_temp(ftp, file_list):
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

    for filename in file_list:
        local_path = os.path.join(TEMP_DIR, filename)
        with open(local_path, "wb") as file:
            ftp.retrbinary(f"RETR {filename}", file.write)
        local_file_path.append(local_path)
        print(f"Downloaded {filename} to {local_path}")
    print("-------------------")

    return TEMP_DIR, local_file_path

def delete_temp_dir(temp_dir):
    """Deletes the temp directory and all its contents."""
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
        print(f"Deleted temp directory: {temp_dir}")
        print("-------------------")

def extract_ucn_from_child_dir_name(child_dir_name):
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

def list_processable_directories(ftp):
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

def collect_directory_contents(ftp, dir_name):
    """
    Collects the contents of a single FTP directory.
    CDs into the directory, checks for HTM files, collects valid
    non-HTM filenames, then CDs back out.

    Args:
        ftp: FTP connection object
        dir_name (str): Name of the directory to inspect.

    Returns:
        dict: {
            "files": list[str] - valid non-HTM filenames,
            "has_htm": bool - True if any .htm or .html file was found
        }
    """
    ftp.cwd(dir_name)

    has_htm = dir_contains_htm_file(ftp)

    files = []
    for filename, attributes in ftp.mlsd(CURRENT_WORKING_DIRECTORY):
        if attributes.get(FILE_METADATA_TYPE) == FTP_TYPE_FILE and is_valid_file(filename, ftp):
            if not filename.lower().endswith((HTM_EXTENSION, HTML_EXTENSION)):
                files.append(filename)

    ftp.cwd(RETURN_TO_PARENT_DIRECTORY)

    return {"files": files, "has_htm": has_htm}

def build_directory_manifest(ftp):
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

# MAIN LOOP SETUP
if __name__ == "__main__":
    try:
        ftp = connect_to_ftp(USERNAME, PASSWORD, FTP_LINK)
        change_directory_911_phone_calls(ABSOLUTE_PATH, ftp)
        manifest = build_directory_manifest(ftp)

        if os.path.exists(TEMP_DIR):
            delete_temp_dir(TEMP_DIR)
# MAIN LOOP
        for child_dir_name, child_dir_data in manifest.items():
            try:
                print("V^V^V^V^V^V^V^V^V^V^V^V^V^V^V^V^V^V^V^V^V^V^V^V^V^V^V^V^V^V^V^V^V^V")
                print(child_dir_name)
                print(f"number of files: {len(child_dir_data['files'])}")
                print("-vvvvvvvvvvvvvvvvvvvvvvv-")

                ftp.cwd(child_dir_name)
                temp_dir, local_file_paths = download_files_to_temp(ftp, child_dir_data["files"])
                ftp.cwd("..")

                ucn = child_dir_data["ucn"]
                reformatted = reformat_unknown_ucn(ucn)
                print(f"Original UCN: {ucn}")
                print(f"Reformatted UCN: {reformatted}")

                is_match = run_stac_script(reformat_unknown_ucn(child_dir_data["ucn"]), local_file_paths, child_dir_name)
                if is_match:
                    delete_temp_dir(temp_dir)
                    if child_dir_data[HAS_HTM_KEY]:
                        rename_directory(ftp, child_dir_name, ERROR_HTM_PREFIX)
                        print(f"HTM file detected — renamed to '{ERROR_HTM_PREFIX}{child_dir_name}', skipping move to Completed.")

                    else:
                        renamed = rename_directory(ftp, child_dir_name, DELETE_DIR_PREFIX)
                        move_to_completed(ftp, renamed, COMPLETED_DIR_NAME)
                else:
                    delete_temp_dir(temp_dir)

            except Exception as e:
                print(f"Failed to process '{child_dir_name}': {e}")
                continue  # move on to the next dir instead of crashing the whole loop.

    except Exception as e:
        print(f"Fatal error during setup: {e}")

# To run this Script use this command to create a log.txt with date and time
# python ftp_conn.py | tee "H:\911_RUN_REPORT_LOGS\log_$(Get-Date -Format 'yyyy-MM-dd_HH-mm-ss').txt"

