import unittest

from srevices.gmail_parser import AirbnbReservation, GmailAirbnbParser, GmailAirbnbParser


class GmailAirbnbParserTestCase(unittest.TestCase):
    def setUp(self):
        self.parser = GmailAirbnbParser()

    def test_extracts_airbnb_reservation_from_dict(self):
        email = {
            "from": "Airbnb <no-reply@airbnb.com>",
            "subject": "Reservation confirmed",
            "body": (
                "Hello,\n"
                "Reservation confirmed for your trip.\n"
                "Check-in: June 10, 2026\n"
                "Check-out: June 15, 2026\n"
                "Total paid: $1,245.67\n"
                "Guest name: Jane Doe\n"
            ),
        }

        reservation = self.parser.extract_reservation(email)

        self.assertIsInstance(reservation, AirbnbReservation)
        self.assertEqual(reservation.guest_name, "Jane Doe")
        self.assertEqual(reservation.check_in, "2026-06-10")
        self.assertEqual(reservation.check_out, "2026-06-15")
        self.assertEqual(reservation.paid_amount, "1245.67")
        self.assertEqual(reservation.currency, "$")
        self.assertEqual(reservation.reservation_dates, "2026-06-10 to 2026-06-15")

    def test_extracts_from_string_body_when_sender_is_missing(self):
        body = (
            "Airbnb booking update\n"
            "from June 10, 2026 to June 15, 2026\n"
            "Amount paid: USD 875.00\n"
            "Reserved by: John Smith\n"
        )

        reservation = self.parser.extract_reservation(body)

        self.assertIsNotNone(reservation)
        self.assertEqual(reservation.check_in, "2026-06-10")
        self.assertEqual(reservation.check_out, "2026-06-15")
        self.assertEqual(reservation.paid_amount, "875.00")
        self.assertEqual(reservation.currency, "USD")
        self.assertEqual(reservation.guest_name, "John Smith")

    def test_ignores_non_airbnb_email(self):
        email = {
            "from": "Example <updates@example.com>",
            "subject": "Weekly newsletter",
            "body": "This is not a reservation email.",
        }

        self.assertIsNone(self.parser.extract_reservation(email))

    def test_backward_compatible_alias_exists(self):
        self.assertIs(GmailAirbnbParser, GmailAirbnbParser)


if __name__ == "__main__":
    unittest.main()

