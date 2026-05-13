import unittest

from srevices.gmail_airbnb_parser import GmailAirbnbReader


class _ReaderWithoutAuth(GmailAirbnbReader):
    def _authenticate(self):
        return None


class GmailAirbnbReaderTestCase(unittest.TestCase):
    def setUp(self):
        self.reader = _ReaderWithoutAuth(credentials_path='client_secret.json', token_path='token.json')

    def test_parse_reservation_confirmed_email_fields(self):
        body = (
            "New booking confirmed! Ellie arrives Apr 26. "
            "Send a message to confirm check-in details or welcome Ellie. "
            "Check-in Sun, Apr 26 3:00 PM "
            "Checkout Wed, May 6 1:00 AM "
            "Guests 2 adults, 1 child, 1 infant "
            "More details about who\'s coming "
            "Confirmation code HMZRQFF2R2 "
            "You earn € 898.94"
        )

        parsed = self.reader.parse_airbnb_email(body)

        self.assertEqual(parsed.get('reservation_id'), 'HMZRQFF2R2')
        self.assertEqual(parsed.get('guests'), '2 adults, 1 child, 1 infant')
        self.assertIsNotNone(parsed.get('guest_counts'))
        self.assertEqual(parsed['guest_counts']['adults'], 2)
        self.assertEqual(parsed['guest_counts']['children'], 1)
        self.assertEqual(parsed['guest_counts']['infants'], 1)
        self.assertEqual(parsed['guest_counts']['total'], 4)
        self.assertEqual(parsed.get('checkin'), 'Sun, Apr 26 3:00 PM')
        self.assertEqual(parsed.get('checkout'), 'Wed, May 6 1:00 AM')
        self.assertEqual(parsed.get('host_payout'), '898.94')

    def test_get_reservations_query_filters_subject(self):
        captured = {}

        def fake_list_messages(query, max_results=50):
            captured['query'] = query
            return []

        self.reader.list_messages = fake_list_messages
        self.reader.get_reservations_for_month(2026, 4)

        self.assertIn('subject:"Reservation confirmed"', captured['query'])

    def test_parse_multiline_table_style_email_fields(self):
        body = (
            "%opentrack%\n\n"
            "NEW BOOKING CONFIRMED! PATRICK ARRIVES JUN 4.\n\n"
            "Check-in     Checkout\n"
            "Thu, Jun 4   Tue, Jun 9\n"
            "3:00 PM      1:00 AM\n\n"
            "GUESTS\n\n"
            "2 adults, 1 child\n\n"
            "MORE DETAILS ABOUT WHO'S COMING\n\n"
            "CONFIRMATION CODE\n"
            "HME3APEFRY\n\n"
            "HOST PAYOUT\n\n"
            "YOU EARN   € 568.58\n"
        )

        parsed = self.reader.parse_airbnb_email(body)

        self.assertEqual(parsed.get('reservation_id'), 'HME3APEFRY')
        self.assertEqual(parsed.get('guests'), '2 adults, 1 child')
        self.assertIsNotNone(parsed.get('guest_counts'))
        self.assertEqual(parsed['guest_counts']['adults'], 2)
        self.assertEqual(parsed['guest_counts']['children'], 1)
        self.assertEqual(parsed['guest_counts']['infants'], 0)
        self.assertEqual(parsed['guest_counts']['total'], 3)
        self.assertEqual(parsed.get('checkin'), 'Thu, Jun 4 3:00 PM')
        self.assertEqual(parsed.get('checkout'), 'Tue, Jun 9 1:00 AM')
        self.assertEqual(parsed.get('host_payout'), '568.58')

    def test_parse_guests_separates_adults_and_children(self):
        guests = self.reader.parse_guests('2 adults, 1 child')

        self.assertEqual(guests['adults'], 2)
        self.assertEqual(guests['children'], 1)
        self.assertEqual(guests['infants'], 0)
        self.assertEqual(guests['total'], 3)

    def test_parse_guests_handles_all_types(self):
        guests = self.reader.parse_guests('2 adults, 1 child, 1 infant')

        self.assertEqual(guests['adults'], 2)
        self.assertEqual(guests['children'], 1)
        self.assertEqual(guests['infants'], 1)
        self.assertEqual(guests['total'], 4)

    def test_parse_guests_handles_singular_forms(self):
        guests = self.reader.parse_guests('1 adult, 2 children')

        self.assertEqual(guests['adults'], 1)
        self.assertEqual(guests['children'], 2)
        self.assertEqual(guests['infants'], 0)
        self.assertEqual(guests['total'], 3)

    def test_parse_guests_handles_empty_string(self):
        guests = self.reader.parse_guests('')

        self.assertEqual(guests['adults'], 0)
        self.assertEqual(guests['children'], 0)
        self.assertEqual(guests['infants'], 0)
        self.assertEqual(guests['total'], 0)

    def test_parse_guests_handles_none(self):
        guests = self.reader.parse_guests(None)

        self.assertEqual(guests['total'], 0)

    def test_extract_guest_names_ner_detects_person_entities(self):
        text = (
            "NEW BOOKING CONFIRMED! PATRICK ARRIVES JUN 4.\n"
            "Hello Spiros, we plan to travel with Patrick and Caro "
            "and our daughter Lucía."
        )

        names = self.reader.extract_guest_names_ner(text)

        self.assertGreater(len(names), 0)
        # Should detect at least the guest names mentioned
        names_lower = [n.lower() for n in names]
        self.assertTrue(any('patrick' in n for n in names_lower))

    def test_extract_guest_names_ner_handles_none(self):
        names = self.reader.extract_guest_names_ner(None)

        self.assertEqual(names, [])

    def test_parse_airbnb_email_includes_ner_guest_names(self):
        body = (
            "NEW BOOKING CONFIRMED! Patrick arrives Jun 4.\n"
            "Hello Spiros, we plan to travel with Patrick.\n"
            "Check-in Thu, Jun 4 3:00 PM\n"
            "Checkout Tue, Jun 9 1:00 AM\n"
            "GUESTS\n2 adults, 1 child\n"
            "CONFIRMATION CODE HME3APEFRY\n"
            "YOU EARN € 568.58\n"
        )

        parsed = self.reader.parse_airbnb_email(body)

        # Should have detected names via NER
        if self.reader.nlp:  # Only if spacy model is loaded
            self.assertIn('guest_names_ner', parsed)
            self.assertGreater(len(parsed['guest_names_ner']), 0)


if __name__ == '__main__':
    unittest.main()

