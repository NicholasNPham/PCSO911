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
FTP_TYPE_DIR = "dir"
FTP_TYPE_FILE = "file"
DELETE_DIR_PREFIX = '_DELETE '
TEMP_DIR =  r"H:\911_TEMP_FILES"

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
    except ftplib.error_perm as e:
        print(f"Login Failed: {e}")
        ftp.quit()
        raise ConnectionError(f"Login Failed: {e}")

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
    except ftplib.error_perm as e:
        print(f"Failed to Changed Directory: {e}")
        ftp.quit()
        raise ConnectionError(f"Failed to Change Directory: {e}")

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
        if ftp.size(filename) > 0:
            return True
        else:
            print(f"File '{filename}' is 0 bytes. Skipping.")
            return False
    except ftplib.error_perm as e:
        print(f"Failed to get size of file: {e}")
        return False

def rename_directory(ftp, old_name, prefix):
    """
    Renames a directory by adding a prefix to its current name.

    Args:
        ftp: FTP connection object
        old_name: current directory name
        prefix: prefix string to prepend to the directory name
    Returns:
        new directory name or None if rename fails
    """
    try:
        new_name = prefix + old_name
        ftp.rename(old_name, prefix + old_name)
        print(f"Renamed '{old_name}' to '{prefix + old_name}'")
        return new_name
    except ftplib.error_perm as e:
        print(f"Failed to rename '{old_name}': {e}")
        return None

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
    except ftplib.error_perm as e:
        print(f"Failed to move '{dir_name}' : {e}")

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

    return TEMP_DIR, local_file_path

def delete_temp_dir(temp_dir):
    """Deletes the temp directory and all its contents."""
    shutil.rmtree(temp_dir)
    print(f"Deleted temp directory: {temp_dir}")

def extract_ucn_from_child_dir_name(child_dir_name):
    """
    Extracts a Universal Case Number (UCN) from a child directory name.

    Args:
        child_dir_name: Name of the child directory to search for a UCN.

    Returns:
        UCN string if found, otherwise None.
    """

    universal_case_number = re.search(UNIVERSAL_CASE_NUMBER_PATTERN, child_dir_name)

    if universal_case_number:
        return universal_case_number.group()
    else:
        return None

def child_dir_name_to_child_dir_filenames_gen(ftp):
    """
    Returns a dictionary mapping child directory names to a list of filenames
    contained within each child directory.

    Args:
        ftp: FTP connection object

    Returns:
        tuple:
            - ftp: FTP connection object
            - child_directory_to_directory_contents_dict (dict): dictionary where
              each key is a child directory name and each value is a list of
              filenames inside that child directory.
              Example: {
                  "child_dir_1": {"UCN": UCN, "files": ["file1.pdf", "file2.mp3"]},
                  "child_dir_2": {"UCN": UCN, "files": ["file3.pdf"]}
              }
    """
    child_directory_to_directory_contents_dict = {}

    for child_directory_name, attribute in ftp.mlsd("."):

        if child_directory_name == COMPLETED_DIR_NAME:
            continue
        elif attribute.get("type") == FTP_TYPE_DIR:
            child_directory_filename_list = []
            ftp.cwd(child_directory_name)
            for filename, attributes in ftp.mlsd("."):
                if attributes.get("type") == FTP_TYPE_FILE and is_valid_file(filename, ftp):
                    child_directory_filename_list.append(filename)

            if child_directory_filename_list:
                ucn = extract_ucn_from_child_dir_name(child_directory_name)
                if ucn is None:
                    print(f"Warning: No UCN found in directory name '{child_directory_name}'. Skipping.")
                    ftp.cwd("..")
                    continue
                child_directory_to_directory_contents_dict[child_directory_name] = {
                    "ucn": ucn,
                    "files": child_directory_filename_list
                }
            else:
                print(f"Warning: No valid files found in '{child_directory_name}'. Skipping.")
            ftp.cwd("..")

    # Uncommit this to check dictionary
    print(child_directory_to_directory_contents_dict)

    return ftp, child_directory_to_directory_contents_dict

# MAIN LOOP SETUP
if __name__ == "__main__":
    try:
        connection = connect_to_ftp(USERNAME, PASSWORD, FTP_LINK)
        ftp, child_directory_to_directory_contents_dict = child_dir_name_to_child_dir_filenames_gen(
            change_directory_911_phone_calls(ABSOLUTE_PATH, connection))

# MAIN LOOP
        for child_dir_name, child_dir_data in child_directory_to_directory_contents_dict.items():
            try:
                print(child_dir_name)
                print(f"number of files: {len(child_dir_data['files'])}")

                ftp.cwd(child_dir_name)
                temp_dir, local_file_paths = download_files_to_temp(ftp, child_dir_data["files"])
                ftp.cwd("..")

                run_stac_script(child_dir_data["ucn"], local_file_paths)

                delete_temp_dir(temp_dir)
                renamed = rename_directory(ftp, child_dir_name, DELETE_DIR_PREFIX)
                if renamed:
                    move_to_completed(ftp, renamed, COMPLETED_DIR_NAME)

            except Exception as e:
                print(f"Failed to process '{child_dir_name}': {e}")
                continue  # move on to the next dir instead of crashing the whole loop.

    except Exception as e:
        print(f"Fatal error during setup: {e}")



