# Standard Library Imports
import ftplib
from ftplib import FTP
import os
import shutil
import random
import string

# Local Imports
from ftp_outlook_error import send_error_email
from key import TEMP_DIR

# CONSTANTS"
FTP_TYPE_FILE = "file"
EMPTY_FILE_SIZE = 0
CURRENT_WORKING_DIRECTORY = '.'
RETURN_TO_PARENT_DIRECTORY = ".."
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