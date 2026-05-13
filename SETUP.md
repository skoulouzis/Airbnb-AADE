# Setup Guide

## Installation

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Download Spacy NER Model (Optional but Recommended)

The spacy NER model enables automatic guest name detection:

```bash
python -m spacy download en_core_web_sm
```

If the download fails, you can also install it with:

```bash
pip install https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.1/en_core_web_sm-3.7.1-py3-none-any.whl
```

## Usage

### Parse Email with NER

```python
from srevices.gmail_airbnb_parser import GmailAirbnbReader

reader = GmailAirbnbReader()

email_body = """
NEW BOOKING CONFIRMED! Patrick arrives Jun 4.

Patrick Aravena
Munich, Germany

Check-in Thu, Jun 4 3:00 PM
Checkout Tue, Jun 9 1:00 AM

GUESTS
2 adults, 1 child

CONFIRMATION CODE
HME3APEFRY

YOU EARN € 568.58
"""

# Parse the email
parsed = reader.parse_airbnb_email(email_body)

# Access extracted data
print(f"Guest: {parsed.get('guest')}")
print(f"Guest names (NER): {parsed.get('guest_names_ner')}")
print(f"Reservation ID: {parsed.get('reservation_id')}")
print(f"Check-in: {parsed.get('checkin')}")
print(f"Check-out: {parsed.get('checkout')}")

# Guest counts
guest_counts = parsed.get('guest_counts')
print(f"Adults: {guest_counts['adults']}")
print(f"Children: {guest_counts['children']}")
print(f"Infants: {guest_counts['infants']}")
print(f"Total: {guest_counts['total']}")

print(f"Host Payout: {parsed.get('host_payout')}")
```

### Direct NER Usage

```python
# Extract just guest names using NER
names = reader.extract_guest_names_ner(email_body)
print(f"Detected names: {names}")
```

### Parse Guest Counts

```python
# Parse guest counts from text
guests_dict = reader.parse_guests("2 adults, 1 child, 1 infant")
print(guests_dict)
# Output: {'adults': 2, 'children': 1, 'infants': 1, 'total': 4}
```

## Features

- **Regex-based parsing**: Fast extraction using patterns for standard Airbnb email fields
- **NER-based guest detection**: Accurate guest name extraction using spacy NER
- **Guest count parsing**: Separates adults, children, and infants
- **Multi-format support**: Handles both inline and table-style layouts
- **Graceful fallback**: Works without spacy (with reduced functionality)

## Troubleshooting

### "No module named 'spacy'"

Make sure to install the dependencies:

```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

### NER not detecting names

If spacy model fails to load, the parser gracefully falls back to regex-only mode. Check the warning message:

```python
reader = GmailAirbnbReader()
print(reader.nlp)  # Will be None if not loaded
```

To verify the model is installed:

```bash
python -c "import spacy; print(spacy.load('en_core_web_sm'))"
```


