# convert.py
#
# This module holds functions for converting a form. This includes CSS
# selectors and JSON extraction.

from __future__ import annotations

import json
from dataclasses import dataclass

from config import EntryInfo
from utils import to_form_url, to_normal_form_url

# Constant freebird component class prefix
FREEBIRD = "freebirdFormviewerComponentsQuestion"

# - FormInfo / QuestionInfo classes
# These mirror the info dicts used by various functions

@dataclass
class FormInfo:
    url: str
    title: str
    description: str
    takes_email: bool
    questions: list[QuestionInfo]

    @classmethod
    def from_soup(cls, soup):
        return cls.from_info(form_info(soup))

    @classmethod
    def from_info(cls, info):
        return cls(
            url=info["form_url"],
            title=info["form_title"],
            description=info["form_description"],
            takes_email=info["takes_email"],
            questions=QuestionInfo.list_from_info(info),
        )

    def to_info(self):
        form = dict(
            form_url=self.url,
            form_title=self.title,
            form_description=self.description,
            takes_email=self.takes_email,
        )
        questions = QuestionInfo.list_to_info(self.questions)
        return form | questions

@dataclass
class QuestionInfo:
    type: str
    title: str
    key: str
    required: bool
    options: Optional[list[str]]

    @classmethod
    def list_from_soup(cls, soup):
        return cls.list_from_info(form_info(soup))

    @classmethod
    def list_from_info(cls, info):
        questions = []
        zipped = zip(
            info["types"], info["titles"], info["keys"],
            info["required"], info["options"],
        )
        for type, title, key, required, options in zipped:
            questions.append(cls(
                type=type, title=title, key=key,
                required=required, options=options,
            ))
        return questions

    @classmethod
    def list_to_info(cls, questions):
        # This needs to be merged with the form info dict
        return dict(
            types=[question.type for question in questions],
            titles=[question.title for question in questions],
            keys=[question.key for question in questions],
            required=[question.required for question in questions],
            options=[question.options for question in questions],
        )

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

# Return body > script (FB_PUBLIC_LOAD_DATA_)
def form_json_data(soup):
    script = soup.select("body>script")[0].contents[0]
    data = script.partition("=")[2].rstrip().removesuffix(";")
    return json.loads(data)

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

# - Form Info

# Return a union of info_using_json and info_using_soup
def form_info(soup):
    return info_using_soup(soup) | info_using_json(form_json_data(soup))

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
