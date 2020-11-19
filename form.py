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
    "Short Answer": format_normal,
    "Paragraph": format_normal,
    "Multiple Choice": format_sentinel,
    "Checkboxes": format_normal,
    "Dropdown": format_sentinel,
    "Date": format_date,
    "Time": format_time,
}
def format_response(entry, type, response, *, required=True):
    if required and not response:
        raise ValueError(f"Entry {entry} is required: {response!r}")
    return FORMATS[type](entry, response)

# Taken from https://docs.google.com/forms/d/e/1FAIpQLSfWiBiihYkMJcZEAOE3POOKXDv6p4Ox4rX_ZRsQwu77aql8kQ/viewform
ENTRIES = {
    2126808200: ["Short Answer", "Short Answer"],
    647036320: ["Paragraph", "Paragraph"],
    363426485: ["Multiple Choice", "Multiple Choice", "Option 1", "Option 2"],
    1142411773: ["Checkboxes", "Checkboxes", "Option 1", "Option 2"],
    2116902388: ["Dropdown", "Dropdown", "Option 1", "Option 2"],
    465882654: ["Date", "Date"],
    1049988990: ["Time", "Time"],
}

# Interactive form input
def form_input(entries):
    data = {}
    for entry, (title, type, *choices) in entries.items():
        # Print title and choices if needed
        print(f" === {title} === ")
        if type in {"Multiple Choice", "Dropdown", "Checkboxes"}:
            for i, choice in enumerate(choices, start=1):
                print(f" [{i}] {choice}")

        # Different input methods for the types
        if type == "Short Answer":
            response = input("Short Answer: (one line) ")
        elif type == "Paragraph":
            print("Paragraph: (empty line to end)")
            lines = []
            while line := input():
                lines.append(line)
            response = "\n".join(lines)
        elif type in {"Multiple Choice", "Dropdown"}:
            index = int(input(f"{type}: (type number in brackets) "))
            response = choices[index - 1]
        elif type == "Checkboxes":
            print("Checkboxes: (type number in brackets, empty line to end)")
            indices = []
            while line := input():
                indices.append(int(line) - 1)
            response = [choices[i] for i in indices]
        elif type == "Date":
            response = input("Date: (format as MM/DD/YYYY) ").split("/")
        elif type == "Time":
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
