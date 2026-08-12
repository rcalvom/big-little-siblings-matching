"""Render one personalized HTML email per recipient from a completed match run.

Reads `pairings.csv` produced by the matcher's private export and writes, for
each recipient, a standalone HTML file plus a recipients CSV that the Thunderbird
composer script consumes.

Two audiences, one file per recipient:

- Littles: one message each, introducing the Big assigned to them.
- Bigs: one message each, listing every Little assigned to that Big.

Rows flagged in `pairings.csv` as coordinator placeholders are skipped: the Big
does not exist, so nobody should receive that message. Nothing here sends mail.
"""

from __future__ import annotations

import argparse
import csv
import html
import re
import sys
from email.headerregistry import Address
from email.message import EmailMessage
from email.policy import SMTP
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_PAIRINGS = (
    BASE_DIR.parent.parent / "outputs" / "fall_2026_v9" / "pairings.csv"
)
DEFAULT_OUTPUT_DIR = BASE_DIR / "rendered"
LITTLE_TEMPLATE = BASE_DIR / "little-email-template.html"
BIG_TEMPLATE = BASE_DIR / "big-email-template.html"

LITTLE_SUBJECT = "¡Conoce a tu Big Sibling! – CSAP Fall 2026"
BIG_SUBJECT = "¡Conoce a tu Little Sibling! – CSAP Fall 2026"
FROM_EMAIL = "csap@purdue.edu"
FROM_NAME = "CSAP at Purdue"

# Bigs who already received a message with fewer Littles and are gaining one
# after telling the coordinator they had room for someone else. Their message
# opens by naming that, so it does not read as a duplicate of the first one.
ADDITIONAL_LITTLE_BIGS = {"B-24", "B-33"}

ADDITIONAL_NOTE = (
    '  <p style="font-size: 15px; margin: 0 0 16px 0;">Como nos comentaste que '
    "estabas interesado en acompa\u00f1ar a alguien m\u00e1s, decidimos sumarte un "
    "<strong>Little Sibling adicional</strong>. Te agradecemos de coraz\u00f3n esa "
    "disposici\u00f3n: para quienes llegan, contar con alguien que los reciba hace "
    "toda la diferencia.</p>\n"
)

CARD_PATTERN = re.compile(r"<!--CARD_START-->(.*?)<!--CARD_END-->", re.DOTALL)


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower())
    return slug.strip("-") or "recipient"


def read_pairings(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"Missing pairings CSV: {path}")
    with path.open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    required = {
        "big_id",
        "big_name",
        "big_email",
        "little_id",
        "little_name",
        "little_email",
        "needs_attention",
    }
    missing = required - set(rows[0] if rows else {})
    if missing:
        raise ValueError(f"Missing columns in {path}: {', '.join(sorted(missing))}")
    return rows


def render_little(template: str, row: dict[str, str]) -> str:
    return (
        template.replace("{{name_little}}", html.escape(row["little_name"]))
        .replace("{{name_big}}", html.escape(row["big_name"]))
        .replace("{{email_big}}", html.escape(row["big_email"]))
    )


def render_big(template: str, big: dict[str, str], littles: list[dict[str, str]]) -> str:
    card_match = CARD_PATTERN.search(template)
    if card_match is None:
        raise ValueError("The Big template must delimit its card with CARD_START/END.")
    card = card_match.group(1)
    cards = "".join(
        card.replace("{{name_little}}", html.escape(row["little_name"])).replace(
            "{{email_little}}", html.escape(row["little_email"])
        )
        for row in littles
    )
    plural = len(littles) > 1
    body = CARD_PATTERN.sub(lambda _: cards, template)
    replacements = {
        "{{additional_note}}": (
            ADDITIONAL_NOTE if big["big_id"] in ADDITIONAL_LITTLE_BIGS else ""
        ),
        "{{name_big}}": html.escape(big["big_name"]),
        "{{banner_heading}}": "¡Conoce a tus Little Siblings!"
        if plural
        else "¡Conoce a tu Little Sibling!",
        "{{card_heading}}": "Tus Little Siblings" if plural else "Tu Little Sibling",
        "{{present_sentence}}": "Queremos presentarte a las personas que vas a acompañar."
        if plural
        else "Queremos presentarte a la persona que vas a acompañar.",
        "{{intro_line}}": "Estos son tus <strong>Little Siblings</strong>:"
        if plural
        else "Este es tu <strong>Little Sibling</strong>:",
        "{{outreach_line}}": "Te animamos a escribirles pronto para presentarte."
        if plural
        else "Te animamos a escribirle pronto para presentarte.",
        "{{arrival_line}}": "están por llegar a un país nuevo y tú eres su primer punto de apoyo en Purdue."
        if plural
        else "está por llegar a un país nuevo y tú eres su primer punto de apoyo en Purdue.",
    }
    for placeholder, value in replacements.items():
        body = body.replace(placeholder, value)
    return body


def plain_text_little(row: dict[str, str]) -> str:
    return f"""Hola, {row['little_name']}:

Ya hicimos tu match en el programa Big-Little Sibling de CSAP. A partir de
ahora cuentas con un estudiante de Purdue que estara disponible para
acompanarte durante tu llegada y tu adaptacion a la vida universitaria en los
Estados Unidos.

Tu Big Sibling es:

  Nombre: {row['big_name']}
  Correo: {row['big_email']}

Te animamos a escribirle pronto para presentarte y empezar a construir esa
conexion antes de tu llegada a Purdue.

Conoce mas sobre Colombia en Purdue: https://csapurdue.com

Abrazos,
Board CSAP 2026-2027
Colombian Student Association at Purdue
"""


def plain_text_big(big: dict[str, str], littles: list[dict[str, str]]) -> str:
    plural = len(littles) > 1
    listing = "\n".join(
        f"  Nombre: {row['little_name']}\n  Correo: {row['little_email']}\n"
        for row in littles
    )
    extra = (
        "\nComo nos comentaste que estabas interesado en acompanar a alguien mas,\n"
        "decidimos sumarte un Little Sibling adicional. Te agradecemos esa\n"
        "disposicion.\n"
        if big["big_id"] in ADDITIONAL_LITTLE_BIGS
        else ""
    )
    return f"""Hola, {big['big_name']}:

Gracias por sumarte como Big Sibling en el programa de CSAP. Queremos
presentarte a {'las personas' if plural else 'la persona'} que vas a acompanar.
{extra}
{'Tus Little Siblings son:' if plural else 'Tu Little Sibling es:'}

{listing}
Te animamos a {'escribirles' if plural else 'escribirle'} pronto para
presentarte. Un mensaje corto de bienvenida antes de su llegada hace una
diferencia enorme.

Conoce mas sobre Colombia en Purdue: https://csapurdue.com

Abrazos,
Board CSAP 2026-2027
Colombian Student Association at Purdue
"""


def write_eml(
    destination: Path,
    *,
    to_name: str,
    to_email: str,
    subject: str,
    text_body: str,
    html_body: str,
    from_email: str,
    from_name: str,
) -> None:
    message = EmailMessage(policy=SMTP)
    message["From"] = Address(display_name=from_name, addr_spec=from_email)
    message["To"] = Address(display_name=to_name, addr_spec=to_email)
    message["Reply-To"] = from_email
    message["Subject"] = subject
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")
    destination.write_bytes(message.as_bytes())


def build(pairings_path: Path, output_dir: Path) -> tuple[int, int, int]:
    rows = read_pairings(pairings_path)
    usable = [row for row in rows if not row["needs_attention"].strip()]
    skipped = len(rows) - len(usable)

    little_template = LITTLE_TEMPLATE.read_text(encoding="utf-8")
    big_template = BIG_TEMPLATE.read_text(encoding="utf-8")

    little_dir = output_dir / "littles"
    big_dir = output_dir / "bigs"
    eml_dir = output_dir / "eml"
    for directory in (little_dir, big_dir, eml_dir):
        directory.mkdir(parents=True, exist_ok=True)

    recipients: list[dict[str, str]] = []

    for index, row in enumerate(sorted(usable, key=lambda r: int(r["little_id"][2:])), 1):
        stem = f"little-{index:02d}-{slugify(row['little_name'])}"
        name = f"{stem}.html"
        body = render_little(little_template, row)
        (little_dir / name).write_text(body, "utf-8")
        write_eml(
            eml_dir / f"{stem}.eml",
            to_name=row["little_name"],
            to_email=row["little_email"],
            subject=LITTLE_SUBJECT,
            text_body=plain_text_little(row),
            html_body=body,
            from_email=FROM_EMAIL,
            from_name=FROM_NAME,
        )
        recipients.append(
            {
                "role": "little",
                "name": row["little_name"],
                "email": row["little_email"],
                "subject": LITTLE_SUBJECT,
                "html_file": str((little_dir / name).relative_to(output_dir)),
            }
        )

    by_big: dict[str, list[dict[str, str]]] = {}
    for row in usable:
        by_big.setdefault(row["big_id"], []).append(row)

    for index, big_id in enumerate(sorted(by_big, key=lambda b: int(b[2:])), 1):
        group = by_big[big_id]
        stem = f"big-{index:02d}-{slugify(group[0]['big_name'])}"
        name = f"{stem}.html"
        body = render_big(big_template, group[0], group)
        (big_dir / name).write_text(body, "utf-8")
        write_eml(
            eml_dir / f"{stem}.eml",
            to_name=group[0]["big_name"],
            to_email=group[0]["big_email"],
            subject=BIG_SUBJECT,
            text_body=plain_text_big(group[0], group),
            html_body=body,
            from_email=FROM_EMAIL,
            from_name=FROM_NAME,
        )
        recipients.append(
            {
                "role": "big",
                "name": group[0]["big_name"],
                "email": group[0]["big_email"],
                "subject": BIG_SUBJECT,
                "html_file": str((big_dir / name).relative_to(output_dir)),
            }
        )

    with (output_dir / "recipients.csv").open("w", encoding="utf-8", newline="") as out:
        writer = csv.DictWriter(
            out, fieldnames=["role", "name", "email", "subject", "html_file"]
        )
        writer.writeheader()
        writer.writerows(recipients)

    return len(usable), len(by_big), skipped


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render personalized match emails as HTML. Sends nothing."
    )
    parser.add_argument("--pairings", type=Path, default=DEFAULT_PAIRINGS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    try:
        littles, bigs, skipped = build(args.pairings, args.output_dir)
    except Exception as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print(f"Rendered {littles} Little emails and {bigs} Big emails in {args.output_dir}")
    if skipped:
        print(f"Skipped {skipped} placeholder row(s); handle those by hand.")
    print("Open any .html in a browser to preview. Nothing was sent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
