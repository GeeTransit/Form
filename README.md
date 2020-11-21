# form.py

Submit a form with just two clicks.

## Quickstart

Go to the [latest release](https://github.com/GeeTransit/Form/releases) and download *form.exe*. Drag a configuration file onto it to open the program. Double clicking it will make it default to using a *config.txt* file.

If you are downloading the source folder, you can run it by activating the virtual environment and running `python form.py <filename>`.

## Setup

Make sure [Python 3.9](https://www.python.org/downloads/release/python-390/) and [Git](https://git-scm.com/downloads) is installed. We'll start by opening a command prompt and cloning the repository.

```cmd
> cd C:\Users\<username>\Documents
> git clone https://github.com/GeeTransit/Form
> cd Form
```

Create a virtual environment and download the required libraries.

```cmd
> python -m venv .venv
> call .venv\scripts\activate
> pip install -r requirements.txt
> deactivate
```

## Usage

Double click *run.bat* to find and use *config.txt* in the current folder. To use a different file, drag it onto *run.bat*.

You can also run the following in case the program window closes immediately.

```cmd
> call .venv\scripts\activate
> python form.py <filename>
> deactivate
```

## Config

The *config.txt* file starts with the link to the Google Form (just copy from the address bar). The following lines have the following form:

```
["*"] ["!"] type "-" key ";" [title] "=" [value]
```

The star `"*"` means that this entry is required. An empty value will be rejected.

The mark `"!"` means that you will be prompted for the value. This would be for sensitive information that you wouldn't want lying around in a file.

The `type` can be one of `"w"`, `"m"`, `"c"`, `"d"`, `"t"`, or `"x"`. They specify different data formats or value parsing. More info is provided in the table below.

| Type   | Description                                     |
|--------|-------------------------------------------------|
| `w`    | Short Answer, Paragraph                         |
| `m`    | Multiple Choice, Dropdown                       |
| `c`    | Checkboxes (comma-separated)                    |
| `d`    | Date (MM/DD/YYYY) or `current` for current date |
| `t`    | Time (HH:MM) or `current` for current time      |
| `x`    | Extra Data                                      |

The `key` identifies the entry. It can be the entry ID in the form `entry.<id>` or just the key in the data (when `type` is `"x"`).

The `title` is a human readable string that identifies the entry. If empty, it defaults to the entry. You can use this to show the question or to keep a description of a data entry.

The `value` is the response to the question, or the value to the key. When the entry is to be prompted, the value will be used if the input is empty (defaults back to the value). If required, this cannot be empty.
