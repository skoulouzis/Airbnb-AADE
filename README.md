# Airbnb Email Reservation Extractor

This project parses email messages from Airbnb and extracts:

- guest name
- reservation check-in and check-out dates
- paid amount
- currency

It also includes a Gmail reader that can download Airbnb emails directly from Gmail using the Gmail API, then save the parsed reservations into a TinyDB database.

## Run the demo

```bash
python main.py --month 5 --year 2025
```

By default, extracted reservations are stored in `reservations_db.json` inside the `reservations` TinyDB table.

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

Airbnb cancellation emails with the subject `Canceled: Reservation` are also included when downloading from Gmail.

Then run:

```bash
python main.py emails.json
```

## Download from Gmail

1. Create OAuth credentials in Google Cloud Console.
2. Save the downloaded client file as `credentials.json`.
3. Run:

```bash
python main.py --month 5 --year 2025
```

The first run opens a browser for Google sign-in and writes a cached token to `token.json`.

You can also narrow the Gmail search with extra terms:

```bash
python main.py --month 5 --year 2025 --query "reservation OR booking" --max-results 20
```

To choose a different TinyDB file or table:

```bash
python main.py --db-path data/reservations.json --table reservations --month 5 --year 2025
```

## Run tests

```bash
python -m unittest discover -s tests
```

## AADE declaration automation

The project includes `srevices/aade_declaration.py` to automate TAXISnet short-term letting declarations.

Use the helper runner:

```bash
AADE_USERNAME="your_username" \
AADE_PASSWORD="your_password" \
AADE_PROPERTY_ID="0000" \
AADE_FIELDS_JSON='{"guestName":"John Doe","arrivalDate":"21/05/2026"}' \
AADE_SCREENSHOTS=true \
AADE_SCREENSHOTS_DIR="aade_screenshots" \
python run_aade_declaration.py
```

To perform a real submit, add `AADE_SUBMIT=true`.

Screenshots are saved for each key step (page open, login submit, redirect, form open, fill, submit) so you can verify the automation flow.

You can also store credentials/config in a JSON file (default path: `aade_credentials.json`):

```json
{
  "username": "your_taxisnet_username",
  "password": "your_taxisnet_password",
  "property_id": "163037",
  "headless": false,
  "submit": false,
  "screenshots": true,
  "screenshots_dir": "aade_screenshots",
  "declaration": {
    "arrival_date":   "21/05/2026",
    "departure_date": "26/05/2026",
    "total_rent":     "350.00",
    "payment_method": "3",
    "platform":       "1",
    "tenant_tin":     "",
    "is_foreigner":   true,
    "passport_id":    "AB123456",
    "notes":          ""
  }
}
```

`payment_method` values: `1` Domestic account · `2` Foreign account · `3` Cash · `4` Other  
`platform` values: `1` Airbnb · `2` Booking.com · `3` Clickstay · `4` HomeAway · `5` Homestay · `6` Luxury Retreats · `7` Only-apartments · `8` TripAdvisor · `9` Other

To use a different JSON path:

```bash
AADE_CREDENTIALS_FILE="/path/to/aade_credentials.json" python run_aade_declaration.py
```

