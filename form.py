from datetime import date, time
from collections import namedtuple

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
    """
    return FORMATS[type](entry, response)

# Parsing functions (one str argument)
def parse_words(response):
    return response
def parse_multiple_choice(response):
    return response

def parse_checkboxes(response):
    responses = list(map(str.strip, response.split(",")))
    if not all(responses):
        raise ValueError("Empty choice in responses: {response}")
    return responses

def parse_date(response):
    month, day, year = response.split("/")
    if len(month) != 2 or len(day) != 2 or len(year) != 4:
        raise ValueError("Incorrect date format: MM/DD/YYYY")
    date(int(year), int(month), int(day))  # Test if date is real
    return [month, day, year]

def parse_time(response):
    hour, minute = response.split(":")
    if len(hour) != 2 or len(minute) != 2:
        raise ValueError("Incorrect time format: HH:MM")
    time(int(hour), int(minute))  # Test if time is real
    return [hour, minute]
def parse_extra(response):
    return response

PARSERS = {
    "w": parse_words,
    "m": parse_multiple_choice,
    "c": parse_checkboxes,
    "d": parse_date,
    "t": parse_time,
    "x": parse_extra,
}
def parse_response(response, type):
    """
    Return a string / list[str] as the response.

    Parse the string using the type. The result should be passed to
    formatters.
    """
    return PARSERS[type](response)

ConfigLine = namedtuple("ConfigLine", "required prompt type entry title value")
def split_config(line):
    """
    Return info on a config file line.

    Parse a string of the format `[*] [!] type - entry ; title = value`.

    Examples:
        w-1000;Question=Default
        !t-1001;Date=
        *m-1001;Class=
        c-1002;Languages=Python,Java,C++
        *!x-emailAddress;Email Address=
    """
    required = (line[0] == "*")
    line = line.removeprefix("*")

    prompt = (line[0] == "!")
    line = line.removeprefix("!")

    type, split, line = line.partition("-")
    if type not in {*"wmcdtx"}:
        raise ValueError(f"Type not valid: {type}")
    if not split:
        raise ValueError("Missing type-entry split '-'")

    entry, split, line = line.partition(";")
    if not entry:
        raise ValueError("Missing entry")
    if not split:
        raise ValueError("Missing entry-title split ';'")

    title, split, value = line.partition("=")
    if not title:
        title = entry  # Title defaults to the entry if absent.
    if not split:
        raise ValueError("Missing title-value split '='")

    entry = entry.strip()
    title = title.strip()
    value = value.strip()

    return ConfigLine(required, prompt, type, entry, title, value)

PROMPTS = {
    "w": "[Text]",
    "m": "[Choice]",
    "c": "[Checkboxes (comma-separated)]",
    "d": "[Date MM/DD/YYYY]",
    "t": "[Time HH:MM]",
    "x": "[Extra Data]",
}

# Change URLs with viewform -> formResponse
def fix_url(url):
    """
    Return a URL that can be POSTed to.

    The url can end with formResponse, or it can end with viewform, which
    is changed to formResponse.
    """
    if not url.endswith("formResponse"):
        if not url.endswith("viewform"):
            raise ValueError("URL cannot be converted into POST link")
        url = url.removesuffix("viewform") + "formResponse"
    return url

# Interactive form input from config file
def form_config(config_file):
    """
    Return a dictionary to be POSTed to the form.

    Use the config_file to create a dictionary containing entries and
    other data. The result should be POSTed to a URL as the data
    argument.
    """
    data = {}
    for config_line in config_file:
        required, prompt, type, entry, title, value = split_config(config_line.rstrip())
        if not prompt:
            if required and not value:
                raise ValueError(f"Response for entry '{title}' is required")
            response = parse_response(value, type)
        else:
            while True:
                line = input(f"{title}: {PROMPTS[type]} ").strip()
                if not line:
                    if required and not value:
                        print(f"Response for entry '{title}' is required")
                        continue
                    print(f"Using default value: {value}")
                    line = value
                try:
                    response = parse_response(line, type)
                except ValueError as e:
                    if not required and not line:
                        # If line isn't empty, it could be a mistake.
                        # Only skip when it is purposefully left empty.
                        break
                    print(repr(e))
                else:
                    break
        data |= format_response(entry, type, response)
    return data

def main():
    import sys
    if len(sys.argv) <= 1 or not sys.argv[1]:
        name = "config.txt"
        print(f"Using default filename: {name}")
    else:
        name = sys.argv[1]
        print(f"Using config file: {name}")

    print("Reading config...")
    with open(name) as file:
        url = fix_url(file.readline().rstrip())
        print(f"Form URL: {url}")
        data = form_config(file)
        print(f"Form data: {data}")

    try:
        import requests
    except ImportError:
        print("Form cannot be submitted (missing requests library)")
        return

    if input("Should the form be submitted? (Y/N) ") not in {*"Yy"}:
        print("Form will not be submitted")
        return

    print("Submitting form...")
    response = requests.post(url, data=data)
    print(f"Response received (200 is good): {response.status_code} {response.reason}")

if __name__ == "__main__":
    try:
        main()
    except:
        import traceback
        traceback.print_exc()
    input("Press enter to close the program...")
