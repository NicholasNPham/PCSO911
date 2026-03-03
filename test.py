from ftplib import FTP
from key import *

host = "ftp.sao10.com"   # replace
username = USERNAME
password = PASSWORD

try:
    ftp = FTP(host, timeout=10)
    ftp.login(username, password)

    print("Connected successfully\n")
    print("Directory Listing:\n")

    ftp.retrlines("LIST")

    ftp.quit()

except Exception as e:
    print("Connection failed:")
    print(e)