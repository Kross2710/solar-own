from datetime import date
from unittest import TestCase

from backend.services.money import payback_block
from providers.evn import EvnTariff


class PaybackEtaTests(TestCase):
    def test_projection_beyond_maximum_date_preserves_payback_progress(self):
        try:
            result = payback_block(
                [], date(2026, 11, 23), EvnTariff(), {},
                0, 1_000, 0, 100_000_000,
            )
        except OverflowError as error:
            self.fail(f"Could not build payback progress: {error}")

        self.assertEqual(result["months_left"], 100_000)
        self.assertIsNone(result["eta"])
        self.assertEqual(result["scenarios"], [])
