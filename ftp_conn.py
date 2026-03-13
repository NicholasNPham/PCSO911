# Standard Library Imports
import ftplib
from ftplib import FTP

# Local Imports
from key import USERNAME, PASSWORD, FTP_LINK, ABSOLUTE_PATH

# CONSTANTS

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
        quit()

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
        quit()

def get_filenames(ftp):
    pass

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

def list_directory_contents(ftp):
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
    child_directory_filename_list = []

    for child_directory_name, attr in ftp.mlsd("."):

        if child_directory_name == "__Completed":
            continue
        elif attr.get("type") == 'dir':
            ftp.cwd(child_directory_name)
            for filename, attrs in ftp.mlsd("."):
                if attrs.get("type") == 'file':
                    child_directory_filename_list.append(filename)
            child_directory_to_directory_contents_dict[child_directory_name] = child_directory_filename_list
            ftp.cwd("..")
            child_directory_filename_list = []

    # Uncommit this to check dictionary
    # print(child_directory_to_directory_contents_dict)

    return ftp, child_directory_to_directory_contents_dict

# MAIN LOOP SETUP
connection = connect_to_ftp(USERNAME, PASSWORD, FTP_LINK)
list_directory_contents(change_directory_911_phone_calls(ABSOLUTE_PATH, connection))

# MAIN LOOP



