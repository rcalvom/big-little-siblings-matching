# Big-Little match mailings — Fall 2026

Turns a finished matching run into one personalized message per participant, and
hands each one to Thunderbird as a prefilled compose window. Nothing here sends
mail: the coordinator reviews every message and presses Send.

## Two audiences

Littles get a message introducing the Big assigned to them. Bigs get one
listing everyone assigned to them, with the wording switching to plural when
that is more than one.

## Running it

```bash
python3 build_match_emails.py                       # render HTML and .eml
python3 open_match_email_composers.py --dry-run     # see who would be opened
python3 open_match_email_composers.py --role big --stop 5
```

`build_match_emails.py` reads the `pairings.csv` that the matcher's private
export produces, so point `DEFAULT_PAIRINGS` at the run you want to send. It
writes `rendered/`, which is ignored by Git because it contains every
participant's name and address: open any file there in a browser to preview.

Useful flags on the composer: `--only` for a single recipient, `--skip`
(repeatable) for people who already received an identical message, `--to` to
redirect every message to yourself for a delivery test, and `--start`/`--stop`
to work in small batches rather than opening sixty windows at once.

## Things worth knowing

The composer strips whitespace between tags before handing the body over.
Thunderbird's CLI renders source indentation as visible line breaks, so the
message arrives with stray gaps without it.

A recipient whose address ends in the reserved `.invalid` domain is a
coordinator placeholder rather than a real person, and is left out of the
mailing instead of being silently included.

`ADDITIONAL_LITTLE_BIGS` names the Bigs who already received a message and are
gaining another Little afterwards. Their message opens by saying so, so it does
not read as a duplicate of the first one. Empty it out for a fresh cohort.

The banner image is loaded from csapurdue.com, so most clients block it until
the reader allows remote images.
