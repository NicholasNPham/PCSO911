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

def get_files(ftp):
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

# Testing Function
def list_directory_contents(ftp):
    """
    lists the contents of a directory and its subdirectories used to only test

    Args:
        ftp: FTP connection object
    Returns:
        ftp connection object
    """
    print(ftp.pwd())

    for filename, attrs in ftp.mlsd("."):
        file_type = attrs.get("type")
        if file_type == "dir":
            print(f'Directory: {filename}')

    print(f"Number of Directories: {len(ftp.nlst())}")

    return ftp

# MAIN LOOP SETUP
connection = connect_to_ftp(USERNAME, PASSWORD, FTP_LINK)
connection = change_directory_911_phone_calls(ABSOLUTE_PATH, connection)

""" This is the test to see if directory contains subdirectories """
# list_directory_contents(change_directory_PSCO911(ABSOLUTE_PATH, connection))

# MAIN LOOP



