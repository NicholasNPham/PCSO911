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
    mail_item = outlook_item.CreateItem(OUTLOOK_MAIL_ITEM)
    mail_item.Subject = subject
    mail_item.BodyFormat = OUTLOOK_BODY_FORMAT
    mail_item.Body = error_in_body

    return mail_item


def send_error_email(outlook_app, error_in_body):
    """
    Creates and sends an error notification email via Outlook.

    Args:
        outlook_app: Outlook application object.
        error_in_body (str): Error message to include in the email body.
    """
    mail_item = create_mailbox_item(outlook_app, MAIL_ITEM_SUBJECT, error_in_body)
    mail_item.To = EMAIL_TO
    mail_item.CC = EMAIL_CC
    mail_item.Send()



