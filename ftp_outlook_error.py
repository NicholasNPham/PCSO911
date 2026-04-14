# THIRD-PARTY IMPORT
import win32com.client

# Local Imports
from key import EMAIL_TO, EMAIL_CC

# CONSTANTS
OUTLOOK_APPLICATION = 'Outlook.Application'
NAMESPACE = 'MAPI'
OUTLOOK_MAIL_ITEM = 0
OUTLOOK_BODY_FORMAT = 1
MAIL_ITEM_SUBJECT = "PSCO911 ERROR!"

# FUNCTIONS
def connect_to_outlook():
    """
    Connect to Microsoft Outlook 2019 and return the MAPI namespace.

    Returns:
        win32com.client.CDispatch: MAPI namespace object used to access
        Outlook folders and data.
    """
    outlook_app = win32com.client.Dispatch(OUTLOOK_APPLICATION)
    namespace = outlook_app.GetNamespace(NAMESPACE)
    return outlook_app, namespace

def create_mailbox_item(outlook_item, subject, error_in_body):
    """
    Creates the mailbox item with the subject and the error message as the body.

    Args:
        outlook_item: Outlook application object
        subject (str): string that lists what script it came from.
        error_in_body (str): the body of the email.

    Returns:
        win32com.client.CDispatch: mail item object ready to be sent.
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

def send_error_email(error_in_body):
    """
    Creates and sends an error notification email via Outlook.

    Args:
        error_in_body (str): Error message to include in the email body.
    """
    try:
        outlook_app, namespace = connect_to_outlook()
        mail_item = create_mailbox_item(outlook_app, MAIL_ITEM_SUBJECT, error_in_body)
        mail_item.To = EMAIL_TO
        mail_item.CC = EMAIL_CC
        mail_item.Send()
    except Exception as send_error_email_error:
        print(f"Failed to send error email: {send_error_email_error}")
        print(f"Original error: {error_in_body}")

