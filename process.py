# process.py
#
# This module holds functions for processing config files. This includes
# prompts, value parsers, and data formatters.

from datetime import date, time, datetime

# - Prompts
# entry -> value

PROMPTS = {
    "words": "[Text]",
    "choice": "[Multiple Choice]",
    "checkboxes": "[Checkboxes (comma-separated)]",
    "date": "[Date MM/DD/YYYY or 'today']",
    "time": "[Time HH:MM or 'now']",
    "extra": "[Extra Data]",
}

def prompt_entry(entry, *, prompts=PROMPTS):
    """
    Prompt for a value to the passed entry.

    Print the entry's title and the appropriate hint (from the prompts dict).
    If the user typed nothing, notify user to the default value (or that it
    will be using an empty value). However, this message won't be printed if
    there's no default value for a required question.
    """
    value = input(f"{entry.title}: {prompts[entry.type]} ").strip()
    if value:
        return value

    if entry.value:
        # Print this if there is a default value
        print(f"Using default value: {entry.value}")
    elif not entry.required:
        # Print this if there's no default but its optional
        print("Using empty value")
    return entry.value

def print_error(error, entry, value):
    """
    Print the error and its reason.
    """
    if entry.required and not value:
        print(f"Value for entry '{entry.title}' is required")
    else:
        print(f"{type(error).__name__}: {', '.join(error.args)}")

# - Parsers
# value -> message

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

# General function (takes a `type` argument)
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

# Entry functions (uses entries)
def parse_entry(entry, value=None):
    """
    Return the parsed value.

    Parse and return the message. If value is None, entry.value will be used.
    If there's an error but the entry is optional and the value is empty, the
    empty value will be returned. If the value isn't empty, the user could have
    tried to enter a parsable value.
    """
    if value is None:
        value = entry.value
    if value:
        return parse_value(value, entry.type)

    if not entry.required:
        # If provided value isn't empty, it could be a mistake. Only
        # skip when it is purposefully left empty.
        return ""
    raise ValueError(f"Value for entry '{entry.title}' is required")

def parse_entries(entries, values=None):
    """
    Return the parsed values.

    Parse and return the messages using parsed_entry. If values is a list, pass
    it as the second argument (value).
    """
    if values is None:
        return list(map(parse_entry, entries))
    else:
        messages = []
        for entry, value in zip(entries, values):
            messages.append(parse_entry(entry, value))
        return messages

# - Prompt & Parse
# If you want to just parse entries without prompting, use parse_entries. These
# functions take an on_prompt and on_error for use in the command line.

def prompt_and_parse_entry(
    entry, *,
    on_prompt=prompt_entry,
    on_error=print_error,
):
    """
    Prompt and return the parsed value.

    Prompt for an entry value and return the message. `on_prompt(entry)` will
    be called to get a value. `on_error(exc, entry, value)` will be called if
    parsing fails. This will loop until `parse_entry(entry, value)` returns
    (without erroring).
    """
    while True:
        value = on_prompt(entry)  # Not in try-except to prevent infinite loop
        try:
            return parse_entry(entry, value)
        except Exception as exc:
            on_error(exc, entry, value)

def prompt_and_parse_entries(
    entries, *,
    on_prompt=prompt_entry,
    on_error=print_error,
):
    """
    Return a list of parsed messages.

    Parse the entries to create a list of messages. If the entry needs a
    prompt, `prompt_and_parse_entry(entry, **kwargs)` is used. Otherwise,
    `parse_entry(entry)` is used. The result should be passed to
    `format_entries`.
    """
    messages = []
    for entry in entries:
        if entry.prompt:
            kwargs = dict(on_prompt=on_prompt, on_error=on_error)
            messages.append(prompt_and_parse_entry(entry, **kwargs))
        else:
            messages.append(parse_entry(entry))
    return messages

# - Formatters
# key, message -> data

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

# Entry functions (uses entries)
def format_entry(entry, message):
    """
    Return a dictionary to be POSTed to the form.

    The rules for format_message apply here as well.
    """
    return format_message(entry.key, entry.type, message)

def format_entries(entries, messages):
    """
    Return a dictionary to be POSTed to the form.

    Format and merge the entries to create a data dictionary containing entries
    and other data. The result should be POSTed to a URL as the data argument.
    """
    data = {}
    for entry, message in zip(entries, messages):
        data |= format_entry(entry, message)
    return data
