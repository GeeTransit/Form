import sys
import traceback

from argparse import ArgumentParser
from configparser import Error as ConfigError
from contextlib import suppress

from config import open_config
from convert import form_info, config_lines_from_info
from process import prompt_entry, parse_entries, format_entries
from utils import to_form_url, url_from_shortcut

# Better parser that allows you to specify converter origin type.
# (Whether it's a file or a shortcut)
parser = ArgumentParser(description="Automate Google Forms")
subparsers = parser.add_subparsers(dest="command", required=True,
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

# form convert --...
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
    with suppress(ValueError):
        to_form_url(origin)
        return "url"
    # Put after checking URL so we can use FileNotFoundError instead of OSError
    with suppress(FileNotFoundError, ConfigError, KeyError):
        url_from_shortcut(origin)
        return "shortcut"
    # Put after shortcut because "file" includes "shortcut"
    with suppress(FileNotFoundError):
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
        sys.exit(1)

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

    # Get the origin mode. This is before checking target because origin comes
    # before target in the command: `convert origin [target]`
    if mode is None:
        mode = get_convert_mode(origin)

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
# arguments that can be passed into parser.parse_args.
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
        args = parser.parse_args(argv)
        main(args)
    except (KeyboardInterrupt, EOFError):
        pass  # Ignore Ctrl+C / Ctrl+Z
    except Exception:  # This won't catch Ctrl+C or sys.exit
        if not simple_run:
            raise
        # Printed and replaced with sys.exit as the user is likely running this
        # using a double click or a drag and drop.
        traceback.print_exc()
        sys.exit(1)
    finally:
        if simple_run:
            with suppress(KeyboardInterrupt, EOFError):
                input("Press enter to close the program...")
