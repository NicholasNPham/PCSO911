# THIRD-PARTY IMPORT
import win32com.client

# Local Imports
from key import EMAIL_TO, EMAIL_CC

# CONSTANTS
OUTLOOK_APPLICATION = 'Outlook.Application'
NAMESPACE = 'MAPI'
OUTLOOK_MAIL_ITEM = 0
OUTLOOK_BODY_FORMAT = 1
MAIL_ITEM_SUBJECT = "PCSO911 ERROR!"

# FUNCTIONS
def connect_to_outlook() -> tuple:
    """
    Connects to Microsoft Outlook 2019 and returns the application and MAPI namespace objects.

    Args:
        None

    Returns:
        tuple: (outlook_app, namespace) where outlook_app is the Outlook Application
               COM object and namespace is the MAPI namespace used to access Outlook data.
    """
    outlook_app = win32com.client.Dispatch(OUTLOOK_APPLICATION)
    namespace = outlook_app.GetNamespace(NAMESPACE)
    return outlook_app, namespace

def create_mailbox_item(outlook_item, subject, error_in_body) -> object:
    """
    Creates the mailbox item with the subject and the error message as the body.

    Args:
        outlook_item: Outlook application object
        subject (str): string that lists what script it came from.
        error_in_body (str): the body of the email.

    Returns:
        Object: mail_item object
    """
    try:
        mail_item = outlook_item.CreateItem(OUTLOOK_MAIL_ITEM)
        mail_item.Subject = subject
        mail_item.BodyFormat = OUTLOOK_BODY_FORMAT
        mail_item.Body = error_in_body

        return mail_item
    except Exception as create_mail_item_error:
        print(f"Failed to send error email: {create_mail_item_error}")
        print(f"Original error: {error_in_body}")
        raise create_mail_item_error

def send_error_email(error_in_body) -> None:
    """
    Creates and sends an error notification email via Outlook.

    Args:
        error_in_body (str): Error message to include in the email body.
    Returns:
        None
    """
    try:
        outlook_app, namespace = connect_to_outlook()
        mail_item = create_mailbox_item(outlook_app, MAIL_ITEM_SUBJECT, error_in_body)
        mail_item.To = EMAIL_TO
        # mail_item.CC = EMAIL_CC
        mail_item.Send()
    except Exception as send_error_email_error:
        print(f"Failed to send error email: {send_error_email_error}")
        print(f"Original error: {error_in_body}")

if __name__ == "__main__":
    send_error_email("TEST: ftp_outlook_error.py is working correctly.")