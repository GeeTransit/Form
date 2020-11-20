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

PROMPTS = {
    "w": "[Text]",
    "m": "[Choice]",
    "c": "[Checkboxes (comma-separated)]",
    "d": "[Date MM/DD/YYYY]",
    "t": "[Time HH:MM]",
}

# Change URLs with viewform -> formResponse
def fix_url(url):
    if not url.endswith("formResponse"):
        if not url.endswith("viewform"):
            raise ValueError("URL cannot be converted into POST link")
        url = url.removesuffix("viewform") + "formResponse"
    return url

# Interactive form input from config file
def form_config(config_file):
    data = {}
    for config_line in config_file:
        prompt, type, key, title, value = split_config(config_line.rstrip())
        if not prompt:
            line = value
        elif line := input(f"{title}: {PROMPTS[type]} ").strip():
            line = line
        else:
            line = value
            print(f"Using default: {line}")

        response = parse_response(line, type)
        data |= format_response(key, type, response)
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
        print("Exiting...")
        return

    if input("Should the form be submitted? (Y/N) ") not in {*"Yy"}:
        print("Exiting...")
        return

    print("Submitting form...")
    response = requests.post(url, data=data)
    print(f"Response: {response.status_code} {response.reason}")

if __name__ == "__main__":
    main()
    input("Press enter to continue...")
