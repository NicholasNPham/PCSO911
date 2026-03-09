# Standard Library Imports
from ftplib import FTP

# Local Imports
from key import USERNAME, PASSWORD, FTP_LINK

# CONSTANTS

# FUNCTIONS
def connect_to_ftp(username, password):
    ftp = FTP(FTP_LINK)
    print(ftp.login(username, password))

# MAIN LOOP SETUP
connection = connect_to_ftp(USERNAME, PASSWORD)



