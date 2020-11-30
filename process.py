# process.py
#
# This module holds functions specifically for parsing config values and for
# returning formatted data dictionaries.

from datetime import date, time, datetime

# - Prompts

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

# - Parsers

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

# - Formatters

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
