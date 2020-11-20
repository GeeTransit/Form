# form.py

Submit a form with just two clicks.

## Usage

Double click *form.py* or run `python form.py`. It will default to finding *config.txt*, failing if not found. You can optionally drag another file on it or run `python form.py other.txt` to use the other file as the configuration.

If `requests` isn't installed globally, there can be an error when running. A message can also appear noting the absence of the library. An alternative is to use *run.bat* instead. Run the following to setup the virtual environment.

```cmd
> python -m venv venv
> venv\scripts\activate
> pip install -r requirements.txt
> deactivate
```

Now, double clicking or dragging a file to *run.bat* will use the virtual environment where `requests` exists.

## Config

The *config.txt* file starts with the link to the Google Form (just copy from the address bar). The following lines have the following form:

```
["*"] ["!"] type "-" entry ";" [title] "=" [value]
```

The star "\*" means that this entry is mandatory. An empty value will be rejected.

The mark "!" means that you will be prompted for the value. This would be for sensitive information that you wouldn't want lying around in a file.

The `type` can be one of "w", "m", "c", "d", "t", or "x". They specify different data formats or value parsing. More info is provided in the table below.

| Type | Description                  |
|------|------------------------------|
| w    | Short Answer, Paragraph      |
| m    | Multiple Choice, Dropdown    |
| c    | Checkboxes (comma-separated) |
| d    | Date (MM/DD/YYYY)            |
| t    | Time (HH:MM)                 |
| x    | Extra Data                   |

The `entry` identifies the entry. It can be the entry ID in the form `entry.<id>` or just the key in the data (when `type` is "x").

The `title` is a human readable string that identifies the entry. If empty, it defaults to the entry. You can use this to show the question or to keep a description of a data entry.

The `value` is the response to the question, or the value to the key. When the entry is to be prompted, the value will be used if the input is empty (defaults back to the value). If required, this cannot be empty.
