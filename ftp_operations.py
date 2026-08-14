# Standard Library Imports
import re
from ftplib import FTP

# Local Imports
from ftp_outlook_error import send_error_email
from ftp_to_stac import run_stac_script
from ftp_conn import collect_directory_contents, delete_temp_dir, rename_directory, move_to_completed, download_files_to_temp, random_six_digit_suffix
from key import UNIVERSAL_CASE_NUMBER_PATTERN

# CONSTANTS
RETURN_TO_PARENT_DIRECTORY = '..'
COMPLETED_DIR_NAME = "__Completed"
ERROR_HTM_PREFIX = '_ERROR_HTM '
DELETE_DIR_PREFIX = '_DELETE '
SCRIPT_RAN_SUFFIX = ' _SCRIPT '
HAS_HTM_KEY = "has_htm"

CURRENT_WORKING_DIRECTORY = '.'
FILE_METADATA_TYPE = "type"
FTP_TYPE_DIR = "dir"

UCN_SEPARATOR = "-"
UCN_SEQUENCE_GROUP_INDEX = -2
UCN_UNKNOWN_GROUP = "0000"
UCN_CASE_TYPE_INDEX = 2
UCN_CASE_TYPE = "CJ"
UCN_UNKNOWN_REPLACEMENT = "A000"
UCN_TRIM_LENGTH = -3

# FUNCTIONS
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

    return manifest

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