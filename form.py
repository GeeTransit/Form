from dataclasses import dataclass
from datetime import date, time, datetime

TYPES = {"w", "m", "c", "d", "t", "x"}

# Specialized functions (entry, response -> dict[str, str])
def format_normal(entry, response):
    return {f"entry.{entry}": response}

def format_sentinel(entry, response):
    return {f"entry.{entry}": response, f"entry.{entry}_sentinel": ""}

def format_date(entry, response):
    keys = [f"entry.{entry}_month", f"entry.{entry}_day", f"entry.{entry}_year"]
    return dict(zip(keys, response))

def format_time(entry, response):
    keys = [f"entry.{entry}_hour", f"entry.{entry}_minute"]
    return dict(zip(keys, response))

def format_extra(entry, response):
    return {entry: response}

# General formatting function (uses a `type` argument)
FORMATS = {
    "w": format_normal,
    "m": format_sentinel,
    "c": format_normal,
    "d": format_date,
    "t": format_time,
    "x": format_extra,
}
def format_response(entry, type, response):
    """
    Return a dictionary to be POSTed to the form.

    Format the entry and response into a dict using the type. The result
    should be merged to the data dictionary.

    Formatter functions shouldn't raise exceptions if supplied the proper
    response from the parser functions. Don't give a string from
    parse_words to format_time.
    """
    return FORMATS[type](entry, response)

# Parsing functions (one str argument)
def parse_normal(response):
    return response

def parse_checkboxes(response):
    responses = list(map(str.strip, response.split(",")))
    if not all(responses):
        raise ValueError("Empty choice in responses: {response}")
    return responses

def parse_date(response):
    if response == "current":
        return date.today().strftime("%m/%d/%Y").split("/")
    month, day, year = response.split("/")
    if len(month) != 2 or len(day) != 2 or len(year) != 4:
        raise ValueError("Incorrect date format: MM/DD/YYYY")
    date(int(year), int(month), int(day))  # Test if date is real
    return [month, day, year]

def parse_time(response):
    if response == "current":
        return datetime.now().strftime("%H:%M").split(":")
    hour, minute = response.split(":")
    if len(hour) != 2 or len(minute) != 2:
        raise ValueError("Incorrect time format: HH:MM")
    time(int(hour), int(minute))  # Test if time is real
    return [hour, minute]

PARSERS = {
    "w": parse_normal,
    "m": parse_normal,
    "c": parse_checkboxes,
    "d": parse_date,
    "t": parse_time,
    "x": parse_normal,
}
def parse_response(response, type):
    """
    Return a string / list[str] as the response.

    Parse the string using the type. The result should be passed to
    formatters.

    Parser functions can raise ValueError if the string doesn't match the
    format of the type.
    """
    return PARSERS[type](response)

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

        A string `*!type-key;title=value` would give `EntryInfo(required=True,
        prompt=True, type="type", key="key", title="title", value="value")`.

        Examples of config lines:
            w-1000;Question=Default
            !t-1001;Date=
            *m-1001;Class=
            c-1002;Languages=Python,Java,C++
            *!x-emailAddress;Email Address=
        """
        if not string:
            raise ValueError("Empty entry")
        required = (string[0] == "*")
        string = string.removeprefix("*")

        if not string:
            raise ValueError("Missing type")
        prompt = (string[0] == "!")
        string = string.removeprefix("!")

        type, split, string = string.partition("-")
        if type not in TYPES:
            raise ValueError(f"Type not valid: {type}")
        if not split:
            raise ValueError("Missing type-key split '-'")

        key, split, string = string.partition(";")
        if not key:
            raise ValueError("Missing key")
        if not split:
            raise ValueError("Missing key-title split ';'")

        title, split, value = string.partition("=")
        if not title:
            title = key  # Title defaults to the key if absent.
        if not split:
            raise ValueError("Missing title-value split '='")

        key = key.strip()
        title = title.strip()
        value = value.strip()

        return cls(required, prompt, type, key, title, value)

ID_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")
def to_form_url(string):
    """
    Return a URL that can be POSTed to.

    If the string is already the POST URL (ends in formResponse), it is
    returned. If the string is the GET URL (ends in viewform), it will be
    converted into a POST URL. If the string is the form's ID, it will be
    substituted into a URL.
    """
    if set(string) <= ID_CHARS:
        if len(string) != 56:
            raise ValueError("Form ID not 56 characters long")
        return f"https://docs.google.com/forms/d/e/{string}/formResponse"
    if string.endswith("formResponse"):
        return string
    if not string.endswith("viewform"):
        return string.removesuffix("viewform") + "formResponse"
    raise ValueError(f"String cannot be converted into POST link: {string}")

PROMPTS = {
    "w": "[Text]",
    "m": "[Multiple Choice]",
    "c": "[Checkboxes (comma-separated)]",
    "d": "[Date MM/DD/YYYY]",
    "t": "[Time HH:MM]",
    "x": "[Extra Data]",
}

def prompt_entry(entry):
    """
    Prompt for a value to the passed entry.
    """
    assert entry.prompt
    while True:
        line = input(f"{entry.title}: {PROMPTS[entry.type]} ").strip()
        if not line:
            if entry.required and not entry.value:
                print(f"Response for entry '{entry.title}' is required")
                continue
            print(f"Using default value: {entry.value}")
            line = entry.value
        try:
            return parse_response(line, entry.type)
        except Exception as e:
            if not entry.required and not line:
                # If line isn't empty, it could be a mistake.
                # Only skip when it is purposefully left empty.
                return ""
            print(repr(e))

def entries(config_file):
    """
    Return a dictionary to be POSTed to the form.

    Use the config_file to create a dictionary containing entries and
    other data. The result should be POSTed to a URL as the data
    argument.
    """

def main():
    import sys

    if len(sys.argv) > 2:
        print("Too many arguments. Usage: python form.py [filename]")
        return

    if len(sys.argv) <= 1 or not sys.argv[1]:
        name = "config.txt"
        print(f"Using default filename: {name}")
    else:
        name = sys.argv[1]
        print(f"Using config file: {name}")

    print("Reading config...")
    with open(name) as file:
        url = to_form_url(file.readline().strip())
        print(f"Form URL: {url}")
        entries = [EntryInfo.from_string(line.strip()) for line in file]

    data = {}
    for entry in entries:
        if entry.prompt:
            response = prompt_entry(entry)
        elif entry.required and not entry.value:
            raise ValueError(f"Value for entry '{entry.title}' is required")
        else:
            response = parse_response(entry.value, entry.type)
        data |= format_response(entry.key, entry.type, response)
    print(f"Form data: {data}")

    try:
        import requests
    except ImportError:
        print("Form cannot be submitted (missing requests library)")
        return

    if input("Should the form be submitted? (Y/N) ").strip().lower() != "y":
        print("Form will not be submitted")
        return

    print("Submitting form...")
    response = requests.post(url, data=data)
    print(f"Response received (200s are good): {response.status_code} {response.reason}")

if __name__ == "__main__":
    try:
        main()
    except:
        import traceback
        traceback.print_exc()
    finally:
        input("Press enter to close the program...")
