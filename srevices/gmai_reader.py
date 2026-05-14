from typing import List, Dict, Optional

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from cachetools import cached, TTLCache
from email.utils import parsedate_to_datetime
import os

# Create a TTL cache with a maximum size of 100 and a TTL of 3600 seconds (1 hour)
cache = TTLCache(maxsize=100, ttl=14400)

class GmailReader:
    SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

    def __init__(self, credentials_path='credentials.json', token_path='token.json'):
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.service = self._authenticate()


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


    def _extract_date_from_message(self, message: Dict) -> Optional[str]:
        """Extract the date from message headers."""
        try:
            headers = message.get('payload', {}).get('headers', [])
            for header in headers:
                if header.get('name') == 'Date':
                    date_str = header.get('value', '')
                    # Parse the date string to a datetime object and convert back to ISO format
                    dt = parsedate_to_datetime(date_str)
                    return dt.isoformat()
            return None
        except Exception as e:
            print(f"Error extracting date: {e}")
            return None


    @cached(cache)
    def list_messages(self, query='from:airbnb subject:"Reservation confirmed"', max_results=10) -> List[Dict]:
        results = self.service.users().messages().list(
            userId='me',
            maxResults=max_results,
            q=query
        ).execute()
        messages = results.get('messages', [])
        message_data = list()
        for msg in messages:
            msg_data = self.get_message(msg['id'])
            message_data.append(msg_data)
        return message_data


    def get_message(self, msg_id: str) -> Dict:
        message = self.service.users().messages().get(
            userId='me',
            id=msg_id
        ).execute()
        # Add the extracted date to the message
        message['sent_date'] = self._extract_date_from_message(message)
        return message

