import json
import sys
import traceback

from argparse import ArgumentParser
from collections import namedtuple
from configparser import ConfigParser, Error as ConfigError
from contextlib import suppress
from dataclasses import dataclass
from datetime import date, time, datetime
from string import ascii_letters, digits

# See README's Config section for more info
TYPES = {
    "words": ["w", "word", "text"],
    "choice": ["m", "mc", "multiple choice"],
    "checkboxes": ["c", "checkbox"],
    "date": ["d"],
    "time": ["t"],
    "extra": ["x", "xD", "extra data"],
}

# Specialized functions (key, message -> dict[str, str])
def format_normal(key, message):
    return {f"entry.{key}": message}

def format_sentinel(key, message):
    return {f"entry.{key}": message, f"entry.{key}_sentinel": ""}

def format_date(key, message):
    keys = [f"entry.{key}_month", f"entry.{key}_day", f"entry.{key}_year"]
    return dict(zip(keys, message))

def format_time(key, message):
    keys = [f"entry.{key}_hour", f"entry.{key}_minute"]
    return dict(zip(keys, message))

def format_extra(key, message):
    return {key: message}

# General formatting function (uses a `type` argument)
FORMATS = {
    "words": format_normal,
    "choice": format_sentinel,
    "checkboxes": format_normal,
    "date": format_date,
    "time": format_time,
    "extra": format_extra,
}
def format_message(key, type, message):
    """
    Return a dictionary to be POSTed to the form.

    Format the key and message into a dict using the type. The result should be
    merged to the data dictionary.

    Formatter functions shouldn't raise exceptions if supplied the proper
    message from the parser functions. Don't give a string from parse_words to
    format_time.
    """
    return FORMATS[type](key, message)

# Parsing functions (one str argument)
def parse_normal(value):
    return value

def parse_checkboxes(value):
    messages = list(map(str.strip, value.split(",")))
    if not all(messages):
        raise ValueError(f"Empty choice in value: {value}")
    return messages

def parse_date(value):
    if value in {"current", "today"}:
        value = date.today().strftime("%m/%d/%Y")
    month, day, year = value.split("/")
    if len(month) != 2 or len(day) != 2 or len(year) != 4:
        raise ValueError("Incorrect date format: MM/DD/YYYY")
    date(int(year), int(month), int(day))  # Check if date is real
    return [month, day, year]

def parse_time(value):
    if value in {"current", "now"}:
        value = datetime.now().strftime("%H:%M")
    hour, minute = value.split(":")
    if len(hour) != 2 or len(minute) != 2:
        raise ValueError("Incorrect time format: HH:MM")
    time(int(hour), int(minute))  # Check if time is real
    return [hour, minute]

PARSERS = {
    "words": parse_normal,
    "choice": parse_normal,
    "checkboxes": parse_checkboxes,
    "date": parse_date,
    "time": parse_time,
    "extra": parse_normal,
}
def parse_value(value, type):
    """
    Return a string / list[str] as the message.

    Parse the string using the type. The result should be passed to
    format_message.

    Parser functions can raise ValueError if the string doesn't match the
    format of the type.
    """
    return PARSERS[type](value)

@dataclass
class EntryInfo:
    required: bool
    prompt: bool
    type: str
    key: str
    title: str
    value: str

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
        for name, aliases in TYPES.items():
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

def url_from_shortcut(shortcut):
    """
    Return the URL from an internet shortcut.
    """
    parser = ConfigParser()
    parser.read(shortcut)
    return parser["InternetShortcut"]["URL"]

def to_normal_form_url(string):
    """
    Return a URL that can be GETted.

    Same rules as to_form_url. The result ends with viewform instead of
    formResponse.
    """
    return to_form_url(string).removesuffix("formResponse") + "viewform"

PROMPTS = {
    "words": "[Text]",
    "choice": "[Multiple Choice]",
    "checkboxes": "[Checkboxes (comma-separated)]",
    "date": "[Date MM/DD/YYYY or 'today']",
    "time": "[Time HH:MM or 'now']",
    "extra": "[Extra Data]",
}

def prompt_entry(entry):
    """
    Prompt for a value to the passed entry.
    """
    assert entry.prompt
    while True:
        value = input(f"{entry.title}: {PROMPTS[entry.type]} ").strip()
        if not value:
            if entry.required and not entry.value:
                print(f"Value for entry '{entry.title}' is required")
                continue
            print(f"Using default value: {entry.value}")
            value = entry.value
        try:
            return parse_value(value, entry.type)
        except Exception as e:
            if not entry.required and not value:
                # If provided value isn't empty, it could be a mistake. Only
                # skip when it is purposefully left empty.
                return ""
            print(type(e).__name__, *e.args)

def parse_entries(entries, *, on_prompt=prompt_entry):
    """
    Return a list of parsed messages.

    Parse the entries to create a list of messages. If the entry needs a
    prompt, on_prompt is called with the entry. It should return a message or
    raise an error. The result should be passed to `format_entries`.
    """
    messages = []
    for entry in entries:
        if entry.prompt:
            messages.append(on_prompt(entry))
        elif entry.required and not entry.value:
            raise ValueError(f"Value for entry '{entry.title}' is required")
        else:
            messages.append(parse_value(entry.value, entry.type))
    return messages

def format_entries(entries, messages):
    """
    Return a dictionary to be POSTed to the form.

    Format and merge the entries to create a data dictionary containing entries
    and other data. The result should be POSTed to a URL as the data argument.
    """
    data = {}
    for entry, message in zip(entries, messages):
        data |= format_message(entry.key, entry.type, message)
    return data

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

# Better parser that allows you to specify converter origin type.
# (Whether it's a file or a shortcut)
better = ArgumentParser(description="Automate Google Forms (better)")
subparsers = better.add_subparsers(dest="command", required=True,
    description="All commands form.py supports")

# form process ...
processor = subparsers.add_parser("process", aliases=["p"],
    help="process config file and send form response",
    description="Process config file and send form response")
processor.add_argument("target", default="config.txt", nargs="?",
    help="file to use process config from")

# form convert ...
converter = subparsers.add_parser("convert", aliases=["c"],
    help="convert form into config file",
    description="Convert form into config file")
converter.add_argument("origin",
    help="origin file / url to convert from")
converter.add_argument("target", default="config.txt", nargs="?",
    help="target file to write converted config to")

modes = converter.add_mutually_exclusive_group()
modes.add_argument("-u", "--url", const="url",
    dest="mode", action="store_const",
    help="assume origin is a url")
modes.add_argument("-f", "--file",  const="file",
    dest="mode", action="store_const",
    help="assume origin is an html file")
modes.add_argument("-s", "--shortcut", const="shortcut",
    dest="mode", action="store_const",
    help="assume origin is a shortcut to a url")

# Get and convert the form HTML
def get_html_from_convert(origin, mode):
    if mode == "file":
        with open(origin) as file:
            return file.read()

    if mode == "shortcut":
        url = url_from_shortcut(origin)
    else:
        url = origin

    try:
        import requests
    except ImportError:
        print("Form cannot be converted (missing requests library)")
        sys.exit(3)

    # We're using to_form_url instead of to_normal_form_url. Apparently the
    # -viewform URL doesn't have the form ready immediately but -formResponse
    # does. Maybe its something with the page loading or some JS trickery.
    url = to_form_url(url)
    response = requests.get(url)
    return response.text

# Return what command should be run with target
def get_target_command(target):
    try:
        # Raises error if not convertable (get_convert_mode)
        mode = get_convert_mode(target)
    except ValueError:
        return "process"

    if mode != "file":
        return "convert"

    # If the target ends with .html, it could be a downloaded form
    if target.endswith(".html"):
        return "convert"
    else:
        return "process"

# Return convert mode that could be used on origin
def get_convert_mode(origin):
    with suppress(FileNotFoundError, OSError, ConfigError, KeyError):
        url_from_shortcut(origin)
        return "shortcut"
    with suppress(ValueError):
        to_form_url(origin)
        return "url"
    with suppress(FileNotFoundError, OSError):  # Put after shortcut
        open(origin).close()
        return "file"
    raise ValueError(f"Origin's mode couldn't be detected: {origin}")

# Process the target file and return the data dict. If `should_submit` is True,
# submit the form to the URL and return the response instead. `command_line`
# specifies if printing is allowed and if errors are converted into sys.exit.
def process(target="config.txt", *, command_line=False, should_submit=None):
    if not command_line:
        print_ = lambda *args, **kwargs: None
    else:
        print_ = print

    # Open config file
    print_(f"Opening config file: {target}")
    try:
        file = open(target)
    except FileNotFoundError:
        if not command_line:
            raise
        print_(f"File doesn't exist: {target}")
        sys.exit(2)

    # Read and process the file
    with file:
        print_("Reading config entries...")
        config = open_config(file)
    print_(f"Form URL: {config.url}")

    messages = parse_entries(config.entries, on_prompt=prompt_entry)
    data = format_entries(config.entries, messages)
    print_(f"Form data: {data}")

    if should_submit is not None and not should_submit:  # False
        return data

    # Used to send the form response
    try:
        import requests
    except ImportError:
        if not command_line:
            raise
        print_("Form cannot be submitted (missing requests library)")
        sys.exit(3)

    if command_line and should_submit is None:
        if input("Submit the form data? (Y/N) ").strip().lower() != "y":
            print_("Form will not be submitted")
            return data

    # Send POST request to the URL
    print_("Submitting form...")
    response = requests.post(config.url, data=data)
    print_(f"Response received: {response.status_code} {response.reason}")
    return response

# Convert origin into a config file and save it to target. If `mode` isn't
# specified, detect it using get_convert_mode. `command_line` specifies if
# printing is allowed and if errors are converted into sys.exit.
# `should_overwrite` specifies if the target file can be overwritten should it
# exist.
def convert(
    origin, target="config.txt", mode=None,
    *, command_line=False, should_overwrite=False,
):
    if not command_line:
        print_ = lambda *args, **kwargs: None
    else:
        print_ = print

    # Used to parse the HTML
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        if not command_line:
            raise
        print_("Form cannot be converted (missing beautifulsoup4 library)")
        sys.exit(3)

    # Check if config file can be written to
    try:
        with open(target) as file:
            if not file.read(1):
                raise FileNotFoundError  # File can be written to
    except FileNotFoundError:
        print_(f"Target file doesn't exist or is empty: {target}")
    # File exists and not empty
    else:
        if command_line and should_overwrite is None:
            print_(f"Target file exists and is not empty: {target}")
            answer = input(f"Overwrite the config file? (Y/N) ")
            if answer.strip().lower() != "y":
                print_("File will not be overwritten")
                return
            print_("File will be overwritten")
        elif not should_overwrite:
            raise ValueError(f"File exists and is not empty: {target}")

    if mode is None:
        mode = get_convert_mode(origin)

    print_(f"Getting form HTML source [{mode}]: {origin}")
    text = get_html_from_convert(origin, mode)

    print_("Converting form...")
    soup = BeautifulSoup(text, "html.parser")
    info = info_using_soup(soup) | info_using_json(form_json_data(soup))

    # Write the info to the config file
    print_(f"Writing to config file: {target}")
    with open(target, mode="w") as file:
        for line in config_lines_from_info(info):
            file.write(line + "\n")

    print_(f"Form converted and written to file: {target}")

# Pass in sys.argv[1:]. Returns whether the program was run using a double
# click of drag and dropped on.
def is_simple_run(argv):
    if len(argv) == 0:  # Double click
        return True
    if len(argv) == 1:  # Drag and dropped file is argument
        if argv[0] not in "--help -h process p convert c".split():
            return True
    return False

# Pass in sys.argv[1:]. Assume is_simple_run(argv) is True. Returns converted
# arguments that can be passed into better.parse_args.
def convert_simple_argv(argv):
    if not argv:  # Double click
        return ["process", "config.txt"]
    else:  # Drag and dropped file is argument
        return [get_target_command(argv[0]), argv[0]]

def main(args):
    if args.command in "process p".split():
        return process(args.target, command_line=True)
    if args.command in "convert c".split():
        return convert(args.origin, args.target, args.mode, command_line=True)
    raise ValueError(f"Unknown command: {args.command}")

if __name__ == "__main__":
    argv = sys.argv[1:]
    simple_run = is_simple_run(argv)
    try:
        if simple_run:
            argv = convert_simple_argv(argv)
        args = better.parse_args(argv)
        main(args)
    except Exception:  # This won't catch Ctrl+C or sys.exit
        if not simple_run:
            raise
        # Printed and replaced with sys.exit as the user is likely running this
        # using a double click or a drag and drop.
        traceback.print_exc()
        sys.exit(4)
    finally:
        if simple_run:
            with suppress(BaseException):
                input("Press enter to close the program...")
