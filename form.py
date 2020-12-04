# form.py
#
# This module is the entry point of form.py. You can run this using `python
# form.py` or you can import it using `import form`.

import utils
import config
import process
import convert
import main

# Import more useful stuff directly into form.py
from utils import to_form_url, to_normal_form_url
from config import EntryInfo, open_config
from process import prompt_entry, parse_entries, format_entries
from convert import form_info, entries_from_info, config_lines_from_info

# Check if main should be called
if __name__ == "__main__":
    main.main_from_command_line()
