from collections import namedtuple
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

def test_EntryInfo_from_string():
    # TODO: Add tests for ValueError (maybe use pytest)
    a = EntryInfo(True, True, "words", "key", "title", "value")
    assert EntryInfo.from_string(" *!words-key;title=value ") == a
    assert EntryInfo.from_string(" * ! words - key ; title = value ") == a

    b = EntryInfo(False, False, "words", "key", "key", "")
    assert EntryInfo.from_string("words-key;=") == b
    assert EntryInfo.from_string("w-key;=") == b
    assert EntryInfo.from_string("word-key;=") == b
    assert EntryInfo.from_string("text-key;=") == b

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
    raise ValueError(f"String cannot be converted into POST link: {string}")

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
                # If provided value isn't empty, it could be a mistake.
                # Only skip when it is purposefully left empty.
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

# Each type has their unique question classes
QUESTION_CLASSES = {
    "words": ["TextRoot"],
    "choice": ["RadioRoot", "SelectRoot"],
    "checkboxes": ["CheckboxRoot"],
    "date": ["DateDateInputs"],
    "time": ["TimeRoot"],
    "extra": [""],
}
def question_type(question):
    for type, classes in QUESTION_CLASSES.items():
        for class_ in classes:
            class_ = f"div.freebirdFormviewerComponentsQuestion{class_}"
            if question.select_one(class_):
                return type
    else:
        raise ValueError("Unknown type of question")

# Return body > script (FB_PUBLIC_LOAD_DATA_)
def form_json_data(soup):
    import json
    script = soup.select("body>script")[0].contents[0]
    data = script.partition("=")[2].rstrip().removesuffix(";")
    return json.loads(data)

# Return all input[type=hidden]
# Not working currently (must run JS, only in browser)
def form_raw_keys(form):
    raw_keys = []
    for input in form.select("input[type=hidden]"):
        name = input["name"]
        if "entry" not in name:
            continue
        raw_key = name.removeprefix("entry.").partition("_")[0]
        if raw_key not in raw_keys:
            raw_keys.append(raw_key)
    return raw_keys

# Return the inputs' keys ordered
# Not working currently (must run JS, only in browser)
def order_keys(raw_keys, types):
    # Order: other, time, date, radio/checkbox
    others, times, dates, choices = [], [], [], []
    for index, type in enumerate(types):
        if type == "time":
            times.append(index)
        elif type == "date":
            dates.append(index)
        elif type == "choice":
            choices.append(index)
        else:
            others.append(index)
    indices = [*others, *times, *dates, *choices]
    assert len(indices) == len(types)
    keys = [None] * len(types)
    for index, raw_key in zip(indices, raw_keys):
        keys[index] = raw_key
    return keys

# Get the question title
def question_title(question):
    selection = "div.freebirdFormviewerComponentsQuestionBaseHeader"
    return list(question.select_one(selection).strings)[0]

# Return whether the question is required
def question_required(question):
    selection = "span.freebirdFormviewerComponentsQuestionBaseRequiredAsterisk"
    return bool(question.select_one(selection))

# Get the options, returning None if not applicable
def question_options(question, type=None):
    if type is None:
        type = question_type(question)
    if type not in {"choice", "checkboxes"}:
        return None

    multiple_choice = "div.freebirdFormviewerComponentsQuestionRadioChoice"
    if question.select_one(multiple_choice):
        return [choice.text for choice in question.select(multiple_choice)]

    checkbox = "div.freebirdFormviewerComponentsQuestionCheckboxChoice"
    if question.select_one(checkbox):
        return [choice.text for choice in question.select(checkbox)]

    dropdown = "div.appsMaterialWizMenuPaperselectOption"
    if question.select_one(dropdown):
        # Remove the first choice ("Choose")
        return [choice.text for choice in question.select(dropdown)][1:]

    raise ValueError("Cannot find question's options")

# Get the question root div (ignores non-question types)
def form_questions(form):
    selection = "div.freebirdFormviewerComponentsQuestionBaseRoot"
    return form.select(selection)

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
    return {
        "types": list(map(question_type, questions)),
        "titles": list(map(question_title, questions)),
        "required": list(map(question_required, questions)),
        "options": list(map(question_options, questions)),
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
    for type, title, key, required, options in zip(
        info["types"], info["titles"], info["keys"],
        info["required"], info["options"],
    ):
        if options:
            title = f"{title} ({', '.join(options)})"
        entries.append(EntryInfo(required, True, type, key, title, ""))
    return entries

# Returns the passed config file name
def parse_arguments(argv):
    import sys

    if len(argv) > 2:
        print("Too many arguments. Usage: python form.py <filename>")
        sys.exit(1)

    if len(argv) == 2:
        print(f"Using config file: {argv[1]}")
        return argv[1]

    print("Using default name: config.txt")
    return "config.txt"

# Returns config info of the passed file name
def read_config(name):
    import sys

    print("Opening config file...")
    try:
        file = open(name)
    except FileNotFoundError:
        print(f"File doesn't exist: {name}")
        sys.exit(2)

    with open(name) as file:
        print("Reading config entries...")
        return open_config(file)

def main():
    import sys

    name = parse_arguments(sys.argv)
    config = read_config(name)
    print(f"Form URL: {config.url}")

    messages = parse_entries(config.entries, on_prompt=prompt_entry)
    data = format_entries(config.entries, messages)
    print(f"Form data: {data}")

    try:
        import requests
    except ImportError:
        print("Form will not be submitted (missing requests library)")
        sys.exit(3)

    if input("Submit the form data? (Y/N) ").strip().lower() != "y":
        print("Form will not be submitted")
        return

    print("Submitting form...")
    response = requests.post(config.url, data=data)
    print(f"Response received: {response.status_code} {response.reason}")

if __name__ == "__main__":
    try:
        main()
    # Apparently an empty except catches SystemExit. This prevents it.
    except SystemExit:
        raise
    except Exception:
        import traceback
        import sys
        traceback.print_exc()
        sys.exit(4)
    finally:
        input("Press enter to close the program...")
