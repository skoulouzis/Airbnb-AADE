import os
import base64
import re
from typing import List, Dict, Optional
from datetime import datetime

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

try:
    import spacy
    HAS_SPACY = True
except ImportError:
    spacy = None
    HAS_SPACY = False


class GmailAirbnbReader:
    SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

    def __init__(self, credentials_path='credentials.json', token_path='token.json'):
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.service = self._authenticate()
        self.nlp = self._load_spacy_model()

    def _load_spacy_model(self):
        """Load spacy NER model for name detection. Falls back to None if unavailable."""
        if not HAS_SPACY:
            return None

        try:
            return spacy.load('en_core_web_sm')
        except Exception as e:
            print(f"Warning: Could not load spacy model: {e}")
            return None

    def _authenticate(self):
        creds = None

        # ✅ Load existing token
        if os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(
                self.token_path,
                self.SCOPES
            )

        # ✅ If expired, refresh silently
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())

        # ✅ If no valid creds → login once
        if not creds or not creds.valid:
            flow = InstalledAppFlow.from_client_secrets_file(
                self.credentials_path,
                self.SCOPES
            )
            creds = flow.run_local_server(port=0)

            # Save for future reuse
            with open(self.token_path, 'w') as token:
                token.write(creds.to_json())

        return build('gmail', 'v1', credentials=creds)

    # ---------- Gmail ----------
    def list_messages(self, query='from:airbnb subject:"Reservation confirmed"', max_results=10) -> List[Dict]:
        results = self.service.users().messages().list(
            userId='me',
            maxResults=max_results,
            q=query
        ).execute()

        return results.get('messages', [])

    def get_message(self, msg_id: str) -> Dict:
        return self.service.users().messages().get(
            userId='me',
            id=msg_id
        ).execute()

    def get_body(self, message: Dict) -> Optional[str]:
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

    # ---------- Parsing ----------
    def parse_airbnb_email(self, text: Optional[str]) -> Dict:
        data = {}

        if not text:
            return data

        # Normalize non-breaking spaces that appear in copied Gmail/Airbnb content.
        body = re.sub(r'[\u00A0\u202F]', ' ', text)

        name = re.search(r'Guest[:\s]+(.+)', body)
        if name:
            data['guest'] = name.group(1).strip()

        # Use NER to detect guest names
        detected_names = self.extract_guest_names_ner(body)
        if detected_names:
            data['guest_names_ner'] = detected_names
            # Prefer the first detected name as primary guest if not already extracted
            if not data.get('guest'):
                data['guest'] = detected_names[0]

        reservation_id = re.search(r'Confirmation\s+code\s+([A-Z0-9]+)', body, flags=re.IGNORECASE)
        if not reservation_id:
            reservation_id = re.search(r'/details/([A-Z0-9]{8,})', body)
        if reservation_id:
            data['reservation_id'] = reservation_id.group(1).strip()

        dates = re.search(
            r'(\d{1,2} \w+ \d{4})\s*-\s*(\d{1,2} \w+ \d{4})',
            body
        )
        if dates:
            data['checkin'] = dates.group(1)
            data['checkout'] = dates.group(2)

        # Airbnb reservation emails usually include day/time (without year).
        checkin = re.search(r'Check-in\s+([A-Za-z]{3},\s+[A-Za-z]{3}\s+\d{1,2}\s+\d{1,2}:\d{2}\s*[AP]M)', body)
        if checkin:
            data['checkin'] = checkin.group(1).strip()

        checkout = re.search(r'Checkout\s+([A-Za-z]{3},\s+[A-Za-z]{3}\s+\d{1,2}\s+\d{1,2}:\d{2}\s*[AP]M)', body)
        if checkout:
            data['checkout'] = checkout.group(1).strip()

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

        guests = re.search(
            r'GUESTS\s+(.+?)(?:\s+MORE DETAILS ABOUT WHO\S* COMING|\s+CONFIRMATION CODE|$)',
            body,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if guests:
            data['guests'] = ' '.join(guests.group(1).split())
            data['guest_counts'] = self.parse_guests(data['guests'])

        host_payout = re.search(r'You earn\s+€\s?([\d,.]+)', body, flags=re.IGNORECASE)
        if host_payout:
            data['host_payout'] = host_payout.group(1).strip()

        return data

    def _parse_reservation_date(self, value: str, year_hint: int):
        if not value:
            return None

        for fmt in ('%d %B %Y', '%a, %b %d %I:%M %p', '%a, %b %d'):
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

    # ---------- Business logic ----------
    def get_reservations_for_month(self, year: int, month: int):
        start = datetime(year, month, 1)
        end = datetime(year + (month // 12), (month % 12) + 1, 1)

        query = (
            f"from:airbnb subject:\"Reservation confirmed\" "
            f"after:{start.strftime('%Y/%m/%d')} before:{end.strftime('%Y/%m/%d')}"
        )
        messages = self.list_messages(query=query, max_results=50)

        reservations = []

        for msg in messages:
            msg_data = self.get_message(msg['id'])
            body = self.get_body(msg_data)
            parsed = self.parse_airbnb_email(body)

            if not parsed.get("checkin"):
                continue

            checkin = self._parse_reservation_date(parsed.get('checkin', ''), start.year)
            checkout = self._parse_reservation_date(parsed.get('checkout', ''), start.year)

            if not checkin or not checkout:
                continue

            if checkout < checkin:
                checkout = checkout.replace(year=checkout.year + 1)

            if checkin < end and checkout > start:
                reservations.append(parsed)

        return reservations