import sys
import traceback

from argparse import ArgumentParser
from configparser import Error as ConfigError
from contextlib import suppress
from datetime import date, time, datetime

from config import open_config
from convert import form_info, config_lines_from_info
from utils import to_form_url, url_from_shortcut

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
    *, command_line=False, should_overwrite=None,
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
    info = form_info(soup)

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
    except KeyboardInterrupt:
        pass  # Ignore Ctrl+C
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
