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

# Interactive form input
def form_input(entries):
    data = {}
    for entry, (title, type, *choices) in entries.items():
        # Print title and choices if needed
        print(f" === {title} === ")
        for choice in choices:
            print(f" - {choice}")

        # Different input methods for the types
        if type == "w":
            response = input("Text: (one line) ")
        elif type == "m" :
            response = input("Choice: (type choice) ")
        elif type == "c":
            line = input("Checkboxes: (type choices separated by commas) ")
            responses = [part.strip() for part in line.split(",")]
        elif type == "d":
            response = input("Date: (format as MM/DD/YYYY) ").split("/")
        elif type == "t":
            response = input("Date: (format as HH:MM) ").split(":")
        else:
            raise ValueError(f"Unknown type: {type!r}")

        # Format the responses into a dict
        data |= format_response(entry, type, response)

    # Formatted request payload
    return data


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
