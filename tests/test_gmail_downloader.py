from __future__ import annotations

import base64
import unittest

from srevices.gmail_downloader import DownloadedEmail, GmailDownloader
from srevices.gmail_parser import GmailAirbnbParser


class _FakeExecute:
    def __init__(self, result):
        self.result = result

    def execute(self):
        return self.result


class _FakeMessages:
    def __init__(self, list_result, full_message):
        self.list_result = list_result
        self.full_message = full_message
        self.last_list_kwargs = None
        self.last_get_kwargs = None

    def list(self, **kwargs):
        self.last_list_kwargs = kwargs
        return _FakeExecute(self.list_result)

    def get(self, **kwargs):
        self.last_get_kwargs = kwargs
        return _FakeExecute(self.full_message)


class _FakeUsers:
    def __init__(self, messages):
        self._messages = messages

    def messages(self):
        return self._messages


class _FakeService:
    def __init__(self, messages):
        self._users = _FakeUsers(messages)

    def users(self):
        return self._users


class GmailDownloaderTestCase(unittest.TestCase):
    def setUp(self):
        plain_text = (
            "Hi Jane Doe\n"
            "Check-in: June 10, 2026\n"
            "Check-out: June 15, 2026\n"
            "Total paid: $1,245.67\n"
            "Guest name: Jane Doe\n"
        )
        encoded = base64.urlsafe_b64encode(plain_text.encode("utf-8")).decode("ascii").rstrip("=")
        self.full_message = {
            "id": "message-1",
            "threadId": "thread-1",
            "snippet": "Reservation confirmed",
            "internalDate": "1767225600000",
            "payload": {
                "headers": [
                    {"name": "From", "value": "Airbnb <no-reply@airbnb.com>"},
                    {"name": "Subject", "value": "Reservation confirmed"},
                    {"name": "Date", "value": "Tue, 10 Jun 2026 12:34:56 +0000"},
                ],
                "parts": [
                    {
                        "mimeType": "text/plain",
                        "body": {"data": encoded},
                    }
                ],
            },
        }
        self.messages = _FakeMessages({"messages": [{"id": "message-1"}]}, self.full_message)
        self.service = _FakeService(self.messages)
        self.downloader = GmailDownloader(service=self.service, extra_query="reservation OR booking")

    def test_build_query_combines_airbnb_sender_and_extra_terms(self):
        query = self.downloader.build_query("newer_than:30d")
        self.assertIn("from:airbnb.com", query)
        self.assertIn("from:airbnb", query)
        self.assertIn("reservation OR booking", query)
        self.assertIn("newer_than:30d", query)

    def test_download_airbnb_emails_normalizes_message(self):
        emails = self.downloader.download_airbnb_emails(max_results=5)

        self.assertEqual(len(emails), 1)
        email = emails[0]
        self.assertIsInstance(email, DownloadedEmail)
        self.assertEqual(email.sender, "Airbnb <no-reply@airbnb.com>")
        self.assertEqual(email.subject, "Reservation confirmed")
        self.assertIn("Check-in: June 10, 2026", email.body)
        self.assertEqual(self.messages.last_list_kwargs["userId"], "me")
        self.assertEqual(self.messages.last_get_kwargs["id"], "message-1")

    def test_download_airbnb_reservations_parses_with_gmail_parser(self):
        reservations = self.downloader.download_airbnb_reservations(parser=GmailAirbnbParser(), max_results=5)

        self.assertEqual(len(reservations), 1)
        reservation = reservations[0]
        self.assertEqual(reservation.guest_name, "Jane Doe")
        self.assertEqual(reservation.check_in, "2026-06-10")
        self.assertEqual(reservation.check_out, "2026-06-15")
        self.assertEqual(reservation.paid_amount, "1245.67")
        self.assertEqual(reservation.currency, "$")

    def test_download_airbnb_emails_rejects_invalid_max_results(self):
        with self.assertRaises(ValueError):
            self.downloader.download_airbnb_emails(max_results=0)


if __name__ == "__main__":
    unittest.main()


