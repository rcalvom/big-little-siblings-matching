"""Open prefilled Thunderbird compose windows for the match emails.

Each window arrives addressed, with the subject set and the rendered HTML in the
body, so the operator only has to press Send. Nothing is sent by this script.

Run `build_match_emails.py` first: this reads the `recipients.csv` and the HTML
files it produced.

Use `--role`, `--start`, `--stop`, or `--only` to work in small batches rather
than opening sixty windows at once.
"""

from __future__ import annotations

import argparse
import csv
import re
import subprocess
import sys
import time
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_RENDERED = BASE_DIR / "rendered"
DEFAULT_FROM_EMAIL = "csap@purdue.edu"
DEFAULT_FROM_NAME = "CSAP at Purdue"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Open prefilled Thunderbird compose windows. Sends nothing."
    )
    parser.add_argument("--rendered", type=Path, default=DEFAULT_RENDERED)
    parser.add_argument("--from-email", default=DEFAULT_FROM_EMAIL)
    parser.add_argument("--from-name", default=DEFAULT_FROM_NAME)
    parser.add_argument(
        "--role", choices=["little", "big"], help="Limit to one audience."
    )
    parser.add_argument(
        "--only",
        help="Substring of a name or address; opens just the matching recipients.",
    )
    parser.add_argument(
        "--skip",
        action="append",
        default=[],
        help="Substring of a name or address to leave out. Repeatable, for "
        "recipients who already received an identical message.",
    )
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--stop", type=int)
    parser.add_argument(
        "--to",
        help="Override every recipient address, for a safe end-to-end test.",
    )
    parser.add_argument("--pause", type=float, default=0.75)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def read_recipients(rendered: Path) -> list[dict[str, str]]:
    path = rendered / "recipients.csv"
    if not path.is_file():
        raise FileNotFoundError(f"Missing {path}. Run build_match_emails.py first.")
    with path.open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError(f"No recipients in {path}")
    for row in rows:
        if not (rendered / row["html_file"]).is_file():
            raise FileNotFoundError(f"Missing rendered email: {row['html_file']}")
    return rows


def compact_body(path: Path) -> str:
    """Return the template body, compacted.

    Thunderbird's CLI composer renders source indentation as visible line
    breaks, so whitespace between tags has to go before it reaches the body.
    """

    document = path.read_text(encoding="utf-8")
    match = re.search(r"<body[^>]*>(.*)</body>", document, re.DOTALL | re.IGNORECASE)
    if match is None:
        raise ValueError(f"Missing HTML body in {path}")
    return re.sub(r">\s+<", "><", match.group(1)).strip()


def quote_compose_value(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def open_composer(
    recipient: dict[str, str], body: str, from_email: str, from_name: str, to: str
) -> None:
    """Hand the compose request to Thunderbird without waiting for it to exit.

    When Thunderbird is already running the process returns immediately. When it
    is not, this call *is* the application launch, so waiting on it would block
    until the user quits, and killing the caller would take the window with it.
    Detaching keeps the window alive regardless of what happens to this script.
    """

    options = ",".join(
        [
            f"from={quote_compose_value(f'{from_name} <{from_email}>')}",
            f"to={quote_compose_value(to)}",
            f"subject={quote_compose_value(recipient['subject'])}",
            f"body={quote_compose_value(body)}",
            "format=html",
        ]
    )
    subprocess.Popen(
        ["thunderbird", "-compose", options],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def main() -> int:
    args = parse_args()
    try:
        recipients = read_recipients(args.rendered)
        if args.role:
            recipients = [r for r in recipients if r["role"] == args.role]
        if args.only:
            needle = args.only.casefold()
            recipients = [
                r
                for r in recipients
                if needle in r["name"].casefold() or needle in r["email"].casefold()
            ]
        for needle in args.skip:
            lowered = needle.casefold()
            recipients = [
                r
                for r in recipients
                if lowered not in r["name"].casefold()
                and lowered not in r["email"].casefold()
            ]
        if args.start < 1:
            raise ValueError("--start must be at least 1")
        stop = args.stop or len(recipients)
        selected = recipients[args.start - 1 : stop]
        if not selected:
            raise ValueError("No recipients selected")

        print(f"{len(selected)} compose window(s) to open:")
        for recipient in selected:
            target = args.to or f"{recipient['name']} <{recipient['email']}>"
            print(f"  [{recipient['role']:<6}] {recipient['name']:<28} -> {target}")
        if args.dry_run:
            print("\nDry run: nothing opened.")
            return 0

        for index, recipient in enumerate(selected, start=1):
            body = compact_body(args.rendered / recipient["html_file"])
            target = args.to or f"{recipient['name']} <{recipient['email']}>"
            open_composer(recipient, body, args.from_email, args.from_name, target)
            print(f"Opened {index}/{len(selected)}: {recipient['name']}")
            if index < len(selected):
                time.sleep(args.pause)
    except Exception as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print(f"\nOpened {len(selected)} compose window(s). No email was sent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
