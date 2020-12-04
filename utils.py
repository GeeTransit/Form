# convert.py
#
# This module holds utility functions. (Mostly URL stuff.)

from configparser import ConfigParser
from string import ascii_letters, digits

ID_CHARS = set(ascii_letters + digits + "-_")  # [a-zA-Z0-9_-]
def to_form_url(string):
    """
    Return a URL that can be POSTed to.

    If the string is already the POST URL (ends in formResponse), it is
    returned. If the string is the GET URL (ends in viewform), it will be
    converted into a POST URL. If the string is the form's ID, it will be
    substituted into a URL.
    """
    string = string.strip()
    if set(string) <= ID_CHARS:
        if len(string) != 56:
            raise ValueError("Form ID not 56 characters long")
        return f"https://docs.google.com/forms/d/e/{string}/formResponse"
    if string.endswith("formResponse"):
        return string
    if string.endswith("viewform"):
        return string.removesuffix("viewform") + "formResponse"
    raise ValueError(f"String cannot be converted into form link: {string}")

def to_normal_form_url(string):
    """
    Return a URL that can be GETted.

    Same rules as to_form_url. The result ends with viewform instead of
    formResponse.
    """
    return to_form_url(string).removesuffix("formResponse") + "viewform"

def url_from_shortcut(filename):
    """
    Return the URL from an internet shortcut.
    """
    shortcut = ConfigParser()
    with open(filename) as file:  # The file must exist
        shortcut.read_file(file)
    return shortcut["InternetShortcut"]["URL"]
