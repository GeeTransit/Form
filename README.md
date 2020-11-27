# form.py

Submit a form with just two clicks.

## Quickstart

Go to the [latest release](https://github.com/GeeTransit/Form/releases) and download *form.exe*.

Click on your browser's address bar, select everything (Ctrl+A), and drag it into the same folder as *form.exe*. This will create an internet shortcut. Drag it onto *form.exe* to create a *config.txt* file for the form. You can rename it into something more descriptive.

Open the config file to edit the values. The first line will be a link to the form. Lines starting with a hash (`"#"`) are comments. The other lines are the questions. A line with an exclamation mark (`"!"`) will mean that the program will ask you each time for the value to the question. The value in the file will be the default value.

Send a form response by dragging the config file onto *form.exe*. Double clicking it will make it default to a file named *config.txt*. It will ask you for the values to the questions with an exclamation mark (`"!"`). Pressing enter without typing anything will make it use the value in the config file.

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

Drag an internet shortcut onto *run.bat* to create a config file (placed at *config.txt* by default) for the form. (This is equivalent to `run --convert <shortcut> config.txt`.)

Double click *run.bat* to find and use *config.txt* in the current folder. (`run --process config.txt`) To use a different file, drag it onto *run.bat*. (`run --process <filename>`)

You can also run the following in case the program window closes immediately. Replace `<command>` with the text in `code format` found above.

```cmd
> call .venv\scripts\activate
> <command>
> deactivate
```

## Config

The *config.txt* file starts with the link to the Google Form (just copy from the address bar).

The following lines contain info for each entry and the format is shown below. Empty lines and lines starting with `"#"` are skipped. Spaces between parts are ignored.

```
["*"] ["!"] type "-" key ";" [title] "=" [value]
```

The star `"*"` means that this entry is required. An empty value will be rejected.

The mark `"!"` means that you will be prompted for the value. This would be for sensitive information that you wouldn't want lying around in a file.

The `type` specifies a different data format or value parsing. More info is provided in the table below.

| Type         | Aliases                      | Description                                   |
|--------------|------------------------------|-----------------------------------------------|
| `words`      | `w`, `word`, `text`          | Short Answer, Paragraph                       |
| `choice`     | `m`, `mc`, `multiple choice` | Multiple Choice, Dropdown                     |
| `checkboxes` | `c`, `checkbox`              | Checkboxes (comma-separated)                  |
| `date`       | `d`                          | Date (MM/DD/YYYY) or `today` for current date |
| `time`       | `t`                          | Time (HH:MM) or `now` for current time        |
| `extra`      | `x`, `extra data`            | Extra Data                                    |

The `key` identifies the entry. It can be the entry ID in the form `entry.<id>` or just the key in the data (when `type` is `"extra"`).

The `title` is a human readable string that identifies the entry. If empty, it defaults to the entry. You can use this to show the question or to keep a description of a data entry.

The `value` is the response to the question, or the value to the key. When the entry is to be prompted, the value will be used if the input is empty (defaults back to the value). If required, this cannot be empty.
