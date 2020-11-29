import sys
import traceback

from argparse import ArgumentParser
from collections import namedtuple
from configparser import ConfigParser
from dataclasses import dataclass
from string import ascii_letters, digits

from process import prompt_and_parse_entries, format_entries

@dataclass
class EntryInfo:
    required: bool
    prompt: bool
    type: str
    key: str
    title: str
    value: str

    # See README's Config section for more info
    TYPES = {
        "words": ["w", "word", "text"],
        "choice": ["m", "mc", "multiple choice"],
        "checkboxes": ["c", "checkbox"],
        "date": ["d"],
        "time": ["t"],
        "extra": ["x", "xD", "extra data"],
    }

    @classmethod
    def from_string(cls, string):
        """
        Return info on a config file line.

        Parse a string of the format `[*] [!] type - key ; title = value`.
        Return a dataclass (simple object) with the config info.

        A string "*!type-key;title=value" would give `EntryInfo(required=True,
        prompt=True, type="type", key="key", title="title", value="value")`.

        Examples of config lines:
            w-1000;Question=Default
            ! time - 1001 ; Time = current
            *multiple choice - 1001 ; Class =
            checkbox-1002; Languages = Python, Java, C++
            *! extra-emailAddress; Email Address =
        """
        string = string.strip()

        if not string:
            raise ValueError("Empty entry")
        required = (string[0] == "*")
        string = string.removeprefix("*").strip()

        if not string:
            raise ValueError("Missing type")
        prompt = (string[0] == "!")
        string = string.removeprefix("!").strip()

        type, split, string = map(str.strip, string.partition("-"))
        for name, aliases in cls.TYPES.items():
            if type == name:
                break
            elif type in aliases:
                type = name
                break
        else:
            raise ValueError(f"Type not valid: {type}")
        if not split:
            raise ValueError("Missing type-key split '-'")

        key, split, string = map(str.strip, string.partition(";"))
        if not key:
            raise ValueError("Missing key")
        if not split:
            raise ValueError("Missing key-title split ';'")

        title, split, value = map(str.strip, string.partition("="))
        if not title:
            title = key  # Title defaults to the key if absent.
        if not split:
            raise ValueError("Missing title-value split '='")

        return cls(required, prompt, type, key, title, value)

    def __str__(self):
        return (
            f"{'*'*self.required}{'!'*self.prompt}{self.type}"
            f"-{self.key};{self.title}={self.value}"
        )

def test_entry_from_string():
    # TODO: Add tests for ValueError (maybe use pytest)
    a = EntryInfo(True, True, "words", "key", "title", "value")
    assert EntryInfo.from_string(" *!words-key;title=value ") == a
    assert EntryInfo.from_string(" * ! words - key ; title = value ") == a

    b = EntryInfo(False, False, "words", "key", "key", "")
    assert EntryInfo.from_string("words-key;=") == b
    assert EntryInfo.from_string("w-key;=") == b
    assert EntryInfo.from_string("word-key;=") == b
    assert EntryInfo.from_string("text-key;=") == b

def test_entry_str():
    entry = EntryInfo(True, True, "words", "key", "title", "value")
    assert EntryInfo.from_string(str(entry)) == entry

    line = "*!words-key;title=value"
    assert str(entry) == line
    assert str(EntryInfo.from_string(line)) == line

ID_CHARS = set(ascii_letters + digits + "-_")  # [a-zA-Z0-9_-]
def to_form_url(string):
    """
    Return a URL that can be POSTed to.

    If the string is already the POST URL (ends in formResponse), it is
    returned. If the string is the GET URL (ends in viewform), it will be
    converted into a POST URL. If the string is the form's ID, it will be
    substituted into a URL. If the string is the file name of an internet
    shortcut, find the target URL and check using the rules above.
    """
    string = string.strip()
    # This won't catch the internet shortcut case (file name has a ".")
    if set(string) <= ID_CHARS:
        if len(string) != 56:
            raise ValueError("Form ID not 56 characters long")
        return f"https://docs.google.com/forms/d/e/{string}/formResponse"
    if string.endswith("formResponse"):
        return string
    if string.endswith("viewform"):
        return string.removesuffix("viewform") + "formResponse"

    # If it's an internet shortcut
    try:
        parser = ConfigParser()
        parser.read(string)
        url = parser["InternetShortcut"]["URL"]
    except:
        pass
    else:
        # Allow exceptions from this to propagate
        return to_form_url(url)

    raise ValueError(f"String cannot be converted into form link: {string}")

def to_normal_form_url(string):
    """
    Return a URL that can be GETted.

    Same rules as to_form_url. The result ends with viewform instead of
    formResponse.
    """
    return to_form_url(string).removesuffix("formResponse") + "viewform"

ConfigInfo = namedtuple("ConfigInfo", "url entries")
def open_config(file):
    """
    Open config file and return the URL and entries.
    """
    if isinstance(file, str):
        file = open(file)
    with file:
        url = to_form_url(file.readline())
        entries = []
        for line in file:
            line = line.strip()
            if not line:
                continue
            if line.startswith("#"):
                continue
            entries.append(EntryInfo.from_string(line))
    return ConfigInfo(url, entries)

# Constant freebird component class prefix
FREEBIRD = "freebirdFormviewerComponentsQuestion"

# Each type has their unique question classes
QUESTION_CLASSES = {
    "words": ["TextRoot"],
    "choice": ["RadioRoot", "SelectRoot"],
    "checkboxes": ["CheckboxRoot"],
    "date": ["DateDateInputs"],
    "time": ["TimeRoot"],
}
def question_type(question):
    for type, classes in QUESTION_CLASSES.items():
        for class_ in classes:
            if question.select_one(f"div.{FREEBIRD}{class_}"):
                return type
    else:
        raise ValueError("Unknown type of question")

# Return body > script (FB_PUBLIC_LOAD_DATA_)
def form_json_data(soup):
    import json
    script = soup.select("body>script")[0].contents[0]
    data = script.partition("=")[2].rstrip().removesuffix(";")
    return json.loads(data)

# Return whether the form takes an x-emailAddress
def form_takes_email(form):
    return bool(form.select_one(f"div.{FREEBIRD}BaseRoot input[type=email]"))

# Get the question title
def question_title(question):
    return list(question.select_one(f"div.{FREEBIRD}BaseHeader").strings)[0]

# Return whether the question is required
def question_required(question):
    return bool(question.select_one(f"span.{FREEBIRD}BaseRequiredAsterisk"))

# Get the options, returning None if not applicable
def question_options(question, type=None):
    if type is None:
        type = question_type(question)
    if type not in {"choice", "checkboxes"}:
        return None

    if options := question.select(f"div.{FREEBIRD}RadioChoice"):
        return [choice.text for choice in options]
    if options := question.select(f"div.{FREEBIRD}CheckboxChoice"):
        return [choice.text for choice in options]
    if options := question.select("div.appsMaterialWizMenuPaperselectOption"):
        # Remove the first choice (the "Choose" placeholder)
        return [choice.text for choice in options][1:]

    raise ValueError("Cannot find question's options")

# Get the question root div (ignores non-question types)
def form_questions(form):
    return form.select(f"div.{FREEBIRD}BaseRoot")

# Get form info using JS script (FB_PUBLIC_LOAD_DATA_)
def info_using_json(json):
    questions = json[1][1]
    def get_options(question):
        if options := question[4][0][1]:
            return [option[0] for option in options]
        return None
    return {
        "form_title": json[1][8],
        "form_description": json[1][0],
        "titles": [question[1] for question in questions],
        "keys": [question[4][0][0] for question in questions],
        "required": [bool(question[4][0][2]) for question in questions],
        "options": [get_options(question) for question in questions],
    }

# Get form info using CSS selectors
def info_using_soup(soup):
    questions = form_questions(soup.form)
    takes_email = form_takes_email(soup.form)
    if takes_email:
        questions.pop(0)  # Remove first question (email)
    return {
        "form_url": to_form_url(soup.form["action"]),
        "types": list(map(question_type, questions)),
        "titles": list(map(question_title, questions)),
        "required": list(map(question_required, questions)),
        "options": list(map(question_options, questions)),
        "takes_email": takes_email,
    }

# Test that the info from soup and from json match
def test_info_soup_css():
    import requests
    from bs4 import BeautifulSoup

    form_id = "1FAIpQLSfWiBiihYkMJcZEAOE3POOKXDv6p4Ox4rX_ZRsQwu77aql8kQ"
    url = to_form_url(form_id)

    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")

    info_soup = info_using_soup(soup)
    info_json = info_using_json(form_json_data(soup))

    for key in info_soup.keys() & info_json.keys():
        assert info_soup[key] == info_json[key]

# Create entries from info
# `info` needs "types", "titles", "keys", "required", and "options"
def entries_from_info(info):
    entries = []
    if info["takes_email"]:
        args = (True, True, "extra", "emailAddress", "Email address", "")
        entries.append(EntryInfo(*args))
    for type, title, key, required, options in zip(
        info["types"], info["titles"], info["keys"],
        info["required"], info["options"],
    ):
        if options:
            title = f"{title} ({', '.join(options)})"
        entries.append(EntryInfo(required, True, type, key, title, ""))
    return entries

# Iterator of config lines from info
def config_lines_from_info(info):
    # First line should be a link that you can paste into a browser
    yield to_normal_form_url(info["form_url"])

    # Note that the file was auto-generated
    yield f"# Auto-generated using form.py"

    yield f"# {info['form_title']}"
    for line in info["form_description"].splitlines():
        yield f"#   {line}"

    for entry in entries_from_info(info):
        yield str(entry)

parser = ArgumentParser(description="Automate Google Forms")
parser.add_argument("target", default="config.txt", nargs="?",
    help="file or url to use")
modes = parser.add_mutually_exclusive_group()
modes.add_argument("-p", "--process", action="store_true",
    help="process the target config file and send the response")
modes.add_argument("-c", "--convert", metavar="URL",
    help="convert the form at the url into a config file at target")

# Get and convert the form HTML
def get_html_from_convert(convert):
    if not convert.endswith(".URL"):
        try:
            with open(convert) as file:
                return file.read()
        except (FileNotFoundError, OSError):
            pass

    # Used to get the form HTML
    try:
        import requests
    except ImportError:
        print("Form cannot be converted (missing requests library)")
        sys.exit(3)

    # We're using to_form_url instead of to_normal_form_url. Apparently the
    # -viewform URL doesn't have the form ready immediately but -formResponse
    # does. Maybe its something with the page loading or some JS trickery.
    url = to_form_url(convert)
    response = requests.get(url)
    return response.text

def get_target_action(target):
    # Try using the file as a URL
    try:
        to_form_url(target)
    except ValueError:
        pass
    else:
        return "convert"

    # If the target ends with .html, it could be a downloaded form
    if target.endswith(".html"):
        return "convert"
    else:
        return "process"

def command_line_process(target):
    # Open config file
    print(f"Opening config file: {target}")
    try:
        file = open(target)
    except FileNotFoundError:
        print(f"File doesn't exist: {target}")
        sys.exit(2)

    # Read and process the file
    with file:
        print("Reading config entries...")
        config = open_config(file)
    print(f"Form URL: {config.url}")

    messages = prompt_and_parse_entries(config.entries)  # Use default prompts
    data = format_entries(config.entries, messages)
    print(f"Form data: {data}")

    # Used to send the form response
    try:
        import requests
    except ImportError:
        print("Form cannot be submitted (missing requests library)")
        sys.exit(3)

    if input("Submit the form data? (Y/N) ").strip().lower() != "y":
        print("Form will not be submitted")
        return

    # Send POST request to the URL
    print("Submitting form...")
    response = requests.post(config.url, data=data)
    print(f"Response received: {response.status_code} {response.reason}")

def command_line_convert(origin, target):
    # Used to parse the HTML
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        print("Form cannot be converted (missing bs4 library)")
        sys.exit(3)

    # Check if config file can be written to
    try:
        with open(target) as file:
            if not file.read(1):
                raise FileNotFoundError  # File can be written to
    except FileNotFoundError:
        print(f"Target file doesn't exist or is empty: {target}")
    else:
        print(f"Target file exists and is not empty: {target}")
        answer = input(f"Overwrite the config file? (Y/N) ")
        if answer.strip().lower() != "y":
            print("File will not be overwritten")
            return
        print("File will be overwritten")

    print(f"Getting form HTML source: {origin}")
    text = get_html_from_convert(origin)

    print("Converting form...")
    soup = BeautifulSoup(text, "html.parser")
    info = info_using_soup(soup) | info_using_json(form_json_data(soup))

    # Write the info to the config file
    print("Writing to config file...")
    with open(target, mode="w") as file:
        for line in config_lines_from_info(info):
            file.write(line + "\n")

    print(f"Form converted and written to file: {target}")

def main(args):
    # If neither --process or --convert was specified
    if not args.process and not args.convert:
        if get_target_action(args.target) == "process":
            args.process = True
        else:
            args.process = False
            args.convert, args.target = args.target, "config.txt"

    if args.process:
        command_line_process(args.target)
    if args.convert:
        command_line_convert(args.convert, args.target)

if __name__ == "__main__":
    # Not wrapped by try-finally as the user is likely running this from the
    # command line.
    args = parser.parse_args()

    try:
        main(args)
    except Exception:  # This won't catch Ctrl+C or sys.exit
        traceback.print_exc()
        sys.exit(4)
    finally:
        input("Press enter to close the program...")
