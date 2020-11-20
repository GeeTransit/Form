from collections import namedtuple

# Specialized functions (response -> dict[str, response])
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

# General formatting function (uses a `type` argument)
FORMATS = {
    "w": format_normal,
    "m": format_sentinel,
    "c": format_normal,
    "d": format_date,
    "t": format_time,
}
def format_response(entry, type, response, *, required=True):
    if required and not response:
        raise ValueError(f"Entry {entry} is required: {response!r}")
    return FORMATS[type](entry, response)

# Parsing functions (one str argument)
def parse_words(response):
    return response
def parse_multiple_choice(response):
    return response
def parse_checkboxes(response):
    return list(map(str.strip, response.split(",")))
def parse_date(response):
    return response.split("/")
def parse_time(response):
    return response.split(":")

PARSERS = {
    "w": parse_words,
    "m": parse_multiple_choice,
    "c": parse_checkboxes,
    "d": parse_date,
    "t": parse_time,
}
def parse_response(response, type):
    return PARSERS[type](response)

# Parse a config file line (format `[!] type - key ; title = value`)
# Examples:
# w-1000;Question=Default
# !t-1001;Time=
# c-1002;Languages=Python,Java,C++
ConfigLine = namedtuple("ConfigLine", "prompt type key title value")
def split_config(line):
    prompt = line[0] == "!"
    line = line.removeprefix("!")

    type, split, line = line.partition("-")
    if type not in {*"wmcdt"}:
        raise ValueError(f"Type not valid: {type}")
    if not split:
        raise ValueError("Missing type-key split '-'")

    key, split, line = line.partition(";")
    if not key:
        raise ValueError("Missing key")
    if not split:
        raise ValueError("Missing key-title split ';'")

    title, split, value = line.partition("=")
    if not split:
        raise ValueError("Missing title-value split '='")

    if not title:
        title = key

    return ConfigLine(prompt, type, key.strip(), title.strip(), value.strip())

# Taken from https://docs.google.com/forms/d/e/1FAIpQLSfWiBiihYkMJcZEAOE3POOKXDv6p4Ox4rX_ZRsQwu77aql8kQ/viewform
ENTRIES = {
    2126808200: ["Short Answer", "w"],
    647036320: ["Paragraph", "w"],
    363426485: ["Multiple Choice", "m", "Option 1", "Option 2"],
    1142411773: ["Checkboxes", "c", "Option 1", "Option 2"],
    2116902388: ["Dropdown", "m", "Option 1", "Option 2"],
    465882654: ["Date", "d"],
    1049988990: ["Time", "t"],
}

PROMPTS = {
    "w": "Text: (one line)",
    "m": "Choice: (type choice)",
    "c": "Checkboxes: (type choices separated by commas)",
    "d": "Date: (format as MM/DD/YYYY)",
    "t": "Date: (format as HH:MM)",
}

# Interactive form input
def form_input(entries):
    data = {}
    for entry, (title, type, *choices) in entries.items():
        # Print title and choices if needed
        print(f" === {title} === ")
        for choice in choices:
            print(f" - {choice}")

        # Different input methods for the types
        line = input(PROMPTS[type] + " ")

        # Parse the given input
        response = parse_response(line, type)

        # Format the responses into a dict
        data |= format_response(entry, type, response)

    # Formatted request payload
    return data

# Interactive form input from config file
FormData = namedtuple("FormData", "url data")
def form_config(file):
    url = file.readline().rstrip()  # Remove trailing newline
    if not url.endswith("formResponse"):
        if not url.endswith("viewform"):
            raise ValueError("URL cannot be converted into POST link")
        url = url.removesuffix("viewform") + "formResponse"

    data = {}
    for line in file:
        line = line.rstrip()  # Remove trailing newline
        prompt, type, key, title, value = split_config(line)
        if not prompt:
            response = value
        else:
            print(f" === {title} === ")
            # Different input prompts for the types
            if line := input(PROMPTS[type] + " ").strip():
                response = line
            else:
                print(f"Using default: {value}")
                response = value

        response = parse_response(value, type)
        data |= format_response(key, type, response)

    return FormData(url, data)

def main():
    import requests
    LINK = "https://docs.google.com/forms/d/e/1FAIpQLSfWiBiihYkMJcZEAOE3POOKXDv6p4Ox4rX_ZRsQwu77aql8kQ/formResponse"

    data = form_input(ENTRIES)
    print(data)

    response = requests.post(LINK, data=data)
    print(response.status_code, response.reason)

    input("Press enter to continue...")

if __name__ == "__main__":
    main()
    input("Press enter to continue...")
