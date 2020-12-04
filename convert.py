# convert.py
#
# This module holds functions for converting a form. This includes CSS
# selectors and JSON extraction.

import json

from config import EntryInfo
from utils import to_form_url, to_normal_form_url

# Constant freebird component class prefix
FREEBIRD = "freebirdFormviewerComponentsQuestion"

# - CSS Selectors

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

# Get the question root div (ignores non-question types)
def form_questions(form):
    return form.select(f"div.{FREEBIRD}BaseRoot")

# Return whether the form takes an x-emailAddress
def form_takes_email(form):
    return bool(form.select_one(f"div.{FREEBIRD}BaseRoot input[type=email]"))

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

# Get the question title
def question_title(question):
    # .strings returns two strings: ["Question", "*" if required]
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

# - JSON Data

# Return script's JSON
def form_json_data(soup):
    # This returns `JSON` from a string with this format:
    #   var FB_PUBLIC_LOAD_DATA_ = JSON;
    script = soup.select("body>script")[0].string
    data = script.partition("=")[2].rstrip().removesuffix(";")
    return json.loads(data)

# Get form info using JS script
def info_using_json(json):
    # Note that most of these were found by matching up strings with the form.
    # They can probably change and so should only be used when necessary (such
    # as for the entry keys).
    questions = json[1][1]
    def get_options(question):
        if options := question[4][0][1]:
            return [option[0] for option in options]
        return None
    return {
        "form_title": json[1][8],
        "form_description": json[1][0] or "",  # Can be None
        "titles": [question[1] for question in questions],
        "keys": [question[4][0][0] for question in questions],
        "required": [bool(question[4][0][2]) for question in questions],
        "options": [get_options(question) for question in questions],
    }

# - Form Info

# Return a union of info_using_json and info_using_soup
def form_info(soup):
    return info_using_soup(soup) | info_using_json(form_json_data(soup))

# Create entries from info
# `info` needs "types", "titles", "keys", "required", and "options"
def entries_from_info(info):
    entries = []

    if info["takes_email"]:
        # Add special entry of type extra for the address
        args = (True, True, "extra", "emailAddress", "Email address", "")
        entries.append(EntryInfo(*args))

    # Add the normal questions
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
    yield "# Auto-generated using form.py"

    # Put the form title / description for convenience
    yield f"# {info['form_title']}"
    # Note that "".splitlines() returns [] (meaning nothing is yielded)
    for line in info["form_description"].splitlines():
        yield f"#   {line}"

    for entry in entries_from_info(info):
        yield str(entry)

# - Tests

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
