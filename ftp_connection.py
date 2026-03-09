# Standard Library Imports
from ftplib import FTP

# Local Imports
from key import USERNAME, PASSWORD, FTP_LINK

# CONSTANTS
LOGIN_SUCCESSFUL = "2"

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

    if status[0] == LOGIN_SUCCESSFUL:
        print("Login Successful")
        return ftp
    else:
        return None

# MAIN LOOP SETUP
connection = connect_to_ftp(USERNAME, PASSWORD, FTP_LINK)
if connection is None:
    print("Connection Failed")

# MAIN LOOP



