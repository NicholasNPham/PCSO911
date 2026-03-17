# Standard Library Imports
import ftplib
from ftplib import FTP
import re

# Local Imports
from key import USERNAME, PASSWORD, FTP_LINK, ABSOLUTE_PATH, UNIVERSAL_CASE_NUMBER_PATTERN

# CONSTANTS
COMPLETED_DIR_NAME = "__Completed"
FTP_TYPE_DIR = "dir"
FTP_TYPE_FILE = "file"

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
                  "child_dir_1": ["file1.pdf", "file2.mp3"],
                  "child_dir_2": ["file3.html"]
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
            ftp.cwd("..")

    # Uncommit this to check dictionary
    print(child_directory_to_directory_contents_dict)

    return ftp, child_directory_to_directory_contents_dict

# MAIN LOOP SETUP
if __name__ == "__main__":
    try:
        connection = connect_to_ftp(USERNAME, PASSWORD, FTP_LINK)
        child_dir_name_to_child_dir_filenames_gen(change_directory_911_phone_calls(ABSOLUTE_PATH, connection))
    except ConnectionError as e:
        print(e)

# MAIN LOOP



