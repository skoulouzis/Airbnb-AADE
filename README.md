# Airbnb Email Reservation Extractor

This project parses email messages from Airbnb and extracts:

- guest name (using regex and NER)
- guest counts (adults, children, infants)
- reservation ID / confirmation code
- check-in and check-out dates
- host payout amount

It also includes a `GmailDownloader` class that can download Airbnb emails directly from Gmail using the Gmail API.

## Installation

```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

The spacy model is optional but recommended for accurate guest name detection via Named Entity Recognition (NER).

## Run the demo

```bash
python main.py
```

## Parse your own emails

Create a JSON file containing either:

- a list of email objects, or
- an object with an `emails` key that contains the list

Each email object can include keys like:

- `from`
- `subject`
- `body`
- `text`
- `date`
- `received_at`

Example:

```json
[
  {
    "from": "Airbnb <no-reply@airbnb.com>",
    "subject": "Reservation confirmed",
    "body": "Check-in: June 10, 2026\nCheck-out: June 15, 2026\nTotal paid: $1,245.67\nGuest: Jane Doe"
  }
]
```

Then run:

```bash
python main.py emails.json
```

## Download from Gmail

1. Create OAuth credentials in Google Cloud Console.
2. Save the downloaded client file as `credentials.json`.
3. Run:

```bash
python main.py --download
```

The first run opens a browser for Google sign-in and writes a cached token to `token.json`.

You can also narrow the Gmail search with extra terms:

```bash
python main.py --download --query "reservation OR booking" --max-results 20
```

## Extracted Fields

The parser returns a dictionary with:

- `guest` - primary guest name (detected via regex or NER)
- `guest_names_ner` - list of all guest names detected via NER
- `guest_counts` - dict with `adults`, `children`, `infants`, `total`
- `reservation_id` - confirmation code from Airbnb
- `checkin` - check-in date and time
- `checkout` - check-out date and time
- `guests` - raw guest string (e.g., "2 adults, 1 child")
- `host_payout` - host earnings in EUR

## Run tests

```bash
python -m unittest discover -s tests
```

