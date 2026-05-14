import base64
import re
import subprocess
import sys
from typing import List, Dict, Optional
from datetime import datetime

try:
    import spacy
    HAS_SPACY = True
except ImportError:
    spacy = None
    HAS_SPACY = False


class AirbnbMailParser:
    SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']


    def __init__(self,messages=None):
        self.ensure_model("en_core_web_sm")
        self.nlp = self._load_spacy_model()
        self.messages = messages

    def ensure_model(self,model="en_core_web_sm"):
        try:
            import importlib
            importlib.import_module(model)
        except ImportError:
            subprocess.check_call(
                [sys.executable, "-m", "spacy", "download", model])

    def _load_spacy_model(self):
        """Load spacy NER model for name detection. Falls back to None if unavailable."""
        if not HAS_SPACY:
            return None
        try:
            return spacy.load('en_core_web_sm')
        except Exception as e:
            print(f"Warning: Could not load spacy model: {e}")
            return None

    def get_body(self, message: Dict) -> Optional[str]:
        if isinstance(message.get('body'), str):
            return message['body']

        if isinstance(message.get('text'), str):
            return message['text']

        payload = message.get('payload', {})

        if 'data' in payload.get('body', {}):
            return base64.urlsafe_b64decode(
                payload['body']['data']
            ).decode(errors='ignore')

        for part in payload.get('parts', []):
            if part.get('mimeType') == 'text/plain':
                data = part['body'].get('data')
                if data:
                    return base64.urlsafe_b64decode(data).decode(errors='ignore')

        return None

    def get_subject(self, message: Dict) -> Optional[str]:
        """Extract the subject line from message headers."""
        headers = message.get('payload', {}).get('headers', [])
        for header in headers:
            if header.get('name') == 'Subject':
                return header.get('value')
        return None

    # ---------- Parsing ----------
    def parse_airbnb_email(self, text: Optional[str], subject: Optional[str] = None) -> Dict:
        data = {}

        if not text:
            return data

        # Normalize non-breaking spaces that appear in copied Gmail/Airbnb content.
        body = re.sub(r'[\u00A0\u202F]', ' ', text)

        # First, try to extract guest name from "Identity verified" pattern
        guest_name_identity = self.extract_guest_name(body)
        if guest_name_identity:
            data['guest'] = guest_name_identity

        # Try to extract reservation ID from subject if it's a cancellation email
        # Pattern: "Canceled: Reservation HMD2KFC4JB for May 21 – 26, 2026"
        reservation_id = None
        if subject:
            subject_match = re.search(r'Canceled:\s+Reservation\s+([A-Z0-9]+)', subject, flags=re.IGNORECASE)
            if subject_match:
                reservation_id = subject_match.group(1).strip()
                data['status'] = 'canceled'
            else:
                data['status'] = 'confirmed'
        else:
            data['status'] = 'confirmed'

        # If not found in subject, try body patterns
        if not reservation_id:
            reservation_id = re.search(r'Confirmation\s+code\s+([A-Z0-9]+)', body, flags=re.IGNORECASE)
            if not reservation_id:
                reservation_id = re.search(r'/details/([A-Z0-9]{8,})', body)

        if reservation_id:
            data['reservation_id'] = reservation_id.group(1).strip() if hasattr(reservation_id, 'group') else reservation_id

        # Try to extract dates from subject for cancellation emails
        # Pattern: "Canceled: Reservation HMD2KFC4JB for May 21 – 26, 2026"
        if subject and not data.get('checkin'):
            subject_dates = re.search(
                r'for\s+([A-Za-z]+)\s+(\d{1,2})\s*[–-]\s*(\d{1,2}),?\s*(\d{4})',
                subject,
                flags=re.IGNORECASE
            )
            if subject_dates:
                month_name = subject_dates.group(1)
                start_day = subject_dates.group(2)
                end_day = subject_dates.group(3)
                year = subject_dates.group(4)
                data.setdefault('checkin', f"{month_name} {start_day}, {year}")
                data.setdefault('checkout', f"{month_name} {end_day}, {year}")

        dates = re.search(
            r'(\d{1,2} \w+ \d{4})\s*-\s*(\d{1,2} \w+ \d{4})',
            body
        )
        checkin_line = re.search(r'Check-in:\s*([A-Za-z]+\s+\d{1,2},\s*\d{4})', body, flags=re.IGNORECASE)
        checkout_line = re.search(r'Check-out:\s*([A-Za-z]+\s+\d{1,2},\s*\d{4})', body, flags=re.IGNORECASE)
        if checkin_line:
            data.setdefault('checkin', checkin_line.group(1).strip())
        if checkout_line:
            data.setdefault('checkout', checkout_line.group(1).strip())
        # Fallback for table layout: "Check-in Checkout / Thu, Jun 4 Tue, Jun 9".
        date_table = re.search(
            r'Check-in\s+Checkout\s+([A-Za-z]{3},\s+[A-Za-z]{3}\s+\d{1,2})\s+([A-Za-z]{3},\s+[A-Za-z]{3}\s+\d{1,2})',
            body,
            flags=re.IGNORECASE,
        )
        if date_table:
            data.setdefault('checkin', date_table.group(1).strip())
            data.setdefault('checkout', date_table.group(2).strip())

        time_row = re.search(
            r'Check-in\s+Checkout\s+[A-Za-z]{3},\s+[A-Za-z]{3}\s+\d{1,2}\s+[A-Za-z]{3},\s+[A-Za-z]{3}\s+\d{1,2}\s+(\d{1,2}:\d{2}\s*[AP]M)\s+(\d{1,2}:\d{2}\s*[AP]M)',
            body,
            flags=re.IGNORECASE,
        )
        if date_table and time_row:
            data['checkin'] = f"{date_table.group(1).strip()} {time_row.group(1).strip()}"
            data['checkout'] = f"{date_table.group(2).strip()} {time_row.group(2).strip()}"
        elif dates:
            data.setdefault('checkin', dates.group(1).strip())
            data.setdefault('checkout', dates.group(2).strip())

        guests = re.search(
            r'GUESTS\s+(.+?)(?:\s+MORE DETAILS ABOUT WHO\S* COMING|\s+CONFIRMATION CODE|$)',
            body,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if guests:
            data['guests'] = ' '.join(guests.group(1).split())
            data['guest_counts'] = self.parse_guests(data['guests'])

        host_payout = re.search(r'(?:You earn\s+€|Total paid:\s*[€$£]?)\s?([\d,.]+)', body, flags=re.IGNORECASE)
        if host_payout:
            data['host_payout'] = host_payout.group(1).strip()

        return data

    def _parse_reservation_date(self, value: str, year_hint: int):
        if not value:
            return None

        for fmt in ('%d %B %Y', '%B %d, %Y', '%a, %b %d %I:%M %p', '%a, %b %d'):
            try:
                parsed = datetime.strptime(value, fmt)
                if fmt in ('%a, %b %d %I:%M %p', '%a, %b %d'):
                    parsed = parsed.replace(year=year_hint)
                return parsed
            except ValueError:
                continue

        return None

    def parse_guests(self, guests_str: Optional[str]) -> Dict:
        """Parse guest string like '2 adults, 1 child, 1 infant' into counts.

        Returns:
            Dict with 'adults', 'children', 'infants', and 'total' keys.
        """
        result = {'adults': 0, 'children': 0, 'infants': 0}

        if not guests_str:
            result['total'] = 0
            return result

        adults = re.search(r'(\d+)\s+adults?', guests_str, flags=re.IGNORECASE)
        if adults:
            result['adults'] = int(adults.group(1))

        children = re.search(r'(\d+)\s+children?', guests_str, flags=re.IGNORECASE)
        if children:
            result['children'] = int(children.group(1))

        infants = re.search(r'(\d+)\s+infants?', guests_str, flags=re.IGNORECASE)
        if infants:
            result['infants'] = int(infants.group(1))

        result['total'] = result['adults'] + result['children'] + result['infants']
        return result

    def extract_guest_names_ner(self, text: Optional[str]) -> List[str]:
        """Extract guest names using NER (Named Entity Recognition).

        Uses spacy to identify PERSON entities in the text.
        Returns list of unique names found.
        """
        if not text or not self.nlp:
            return []

        doc = self.nlp(text)
        names = []
        seen = set()

        for ent in doc.ents:
            if ent.label_ == 'PERSON' and ent.text not in seen:
                names.append(ent.text)
                seen.add(ent.text)

        return names

    def extract_guest_name(self, text: Optional[str]) -> Optional[str]:
        """Extract guest name that appears before 'Identity verified' text.

        Looks for text pattern: (Guest name) followed by 'Identity verified'
        Returns the guest name if found.
        """
        if not text:
            return None
        guest_first_name = self.extract_guest_first_name_from_welcome_line(
            text)

        if not guest_first_name:
            return None

        # Prefer scanning the section before "Identity verified" where Airbnb shows the guest profile block.
        identity_index = re.search(r'Identity\s+verified', text, flags=re.IGNORECASE)
        search_area = text[:identity_index.start()] if identity_index else text
        forbidden_all_caps = r'(?:ARRIVES|JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC|JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)'
        pattern = rf'''
        \b{re.escape(guest_first_name)}                              # first name
        (?:(?:[ \t]+|\r?\n(?!\r?\n)))                     # spaces/tabs or single newline (no blank line)
        (?!send\b)                                        # disallow 'Send' token
        (?!{forbidden_all_caps}\b)                        # disallow exact forbidden ALL-CAPS words as last name
        (?!\d+\b)                                         # disallow a purely numeric token (dates)
        (?!\d{{1,2}}[:/.-]\d{{1,2}}(?:[:/.-]\d{{2,4}})?\b) # disallow common date formats like 26, 05/26/2026, 05-26
        [A-ZÄÖÜẞ][A-Za-zÄÖÜäöüß'’-]+                      # last name part 1 (capitalized, allows umlauts/apostrophe/hyphen)
        (?:\s+[A-ZÄÖÜẞ][A-Za-zÄÖÜäöüß'’-]+)?              # optional second capitalized part (e.g., compound surnames)
        \b
        '''
        regex = re.compile(pattern, re.VERBOSE)
        matches = re.findall(regex, search_area)
        if len(matches) == 1:
            return matches[0]
        else:
            return guest_first_name

    def extract_guest_first_name_from_welcome_line(self, text: Optional[str]) -> Optional[str]:
        """Extract first name from Airbnb phrase ending in 'or welcome NAME'."""
        if not text:
            return None

        match = re.search(
            r'Send\s+a\s+message\s+to\s+confirm\s+check-?in\s+details\s+or\s+welcome\s+([A-Za-z][A-Za-z\-\']*)',
            text,
            flags=re.IGNORECASE,
        )
        if not match:
            return None

        matched_name = match.group(1)
        first_name = matched_name.strip(" .,!?:;\"'()[]{}") if matched_name else ""
        return first_name.capitalize() if first_name else None


    def get_reservations(self):
        reservations = []
        for msg_data in self.messages:

            body = self.get_body(msg_data)
            subject = self.get_subject(msg_data)
            parsed = self.parse_airbnb_email(body, subject=subject)

            if not parsed.get("checkin") and not parsed.get("checkout"):
                continue
            # Get the year from message['sent_date']
            year = msg_data['sent_date'][:4] if msg_data.get('sent_date') else None
            if year:
                try:
                    year = int(year)
                except ValueError:
                    year = datetime.now().year
            else:
                year = datetime.now().year
            checkin = self._parse_reservation_date(parsed.get('checkin', ''), year)
            checkout = self._parse_reservation_date(parsed.get('checkout', ''), year)
            #
            parsed['checkin'] = checkin.strftime('%d/%m/%Y')
            parsed['checkout'] = checkout.strftime('%d/%m/%Y')
            reservations.append(parsed)

        cancel_ids = []
        clean_reservations = []
        for reservation in  reservations:
            if reservation['status'] == 'canceled':
                cancel_ids.append(reservation['reservation_id'])
            else:
                clean_reservations.append(reservation)

        for reservation in clean_reservations:
            if reservation['reservation_id'] in cancel_ids:
                reservation['status'] = 'canceled'
        return clean_reservations

