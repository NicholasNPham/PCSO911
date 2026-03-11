# Standard Library Imports
import ftplib
from ftplib import FTP

# Local Imports
from key import USERNAME, PASSWORD, FTP_LINK, ABSOLUTE_PATH

# CONSTANTS
SUCCESS_CODE = "2"
''
# FUNCTIONS
def connect_to_ftp(username, password, ftp_link):
    """
    Connect to FTP server.

    Args:
        username: FTP account username.
        password: FTP account password.
        ftp_link: FTP server address.

    Returns:
        FTP connection object or None if login fails.
    """
    ftp = FTP(ftp_link)
    status = ftp.login(username, password)

    if status[0] == SUCCESS_CODE:
        print("Login Successful")
        return ftp
    else:
        print("Login Failed")
        ftp.quit()
        return None

def change_directory_PSCO911(absolute_path, ftp):
    """
    changing directory to PSCO911

    Args:
        absolute_path: absolute path to directory to change
        ftp: FTP connection object
    Returns:
        ftp connection object or None if change fails.
    """
    status = ftp.cwd(absolute_path)

    if status[0] == SUCCESS_CODE:
        print("Changed Directory Successfully")
        return ftp
    else:
        return None

def list_directory_contents(ftp):

    print(ftp.pwd())

    for filename, attrs in ftp.mlsd("."):
        file_type = attrs.get("type")
        if file_type == "dir":
            print(f'Directory: {filename}')
    print(len(ftp.nlst()))

    return ftp

# MAIN LOOP SETUP
connection = connect_to_ftp(USERNAME, PASSWORD, FTP_LINK)

if connection == None:
    print("Login Failed")
    quit()

list_directory_contents(change_directory_PSCO911(ABSOLUTE_PATH, connection))

# MAIN LOOP



