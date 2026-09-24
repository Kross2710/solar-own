import base64
from unittest import TestCase

from providers.cloud_goodwe import (
    curve_points,
    energy_by_day,
    sems_password,
    sems_signature,
)


class SemsPlusParsingTests(TestCase):
    def test_password_is_base64_of_md5_hex(self) -> None:
        self.assertEqual(sems_password("abc"), "OTAwMTUwOTgzY2QyNGZiMGQ2OTYzZjdkMjhlMTdmNzI=")

    def test_signature_binds_the_timestamp(self) -> None:
        signed = sems_signature("uid", "token", 1000)
        raw = base64.b64decode(signed).decode("ascii")
        digest, stamp = raw.rsplit("@", 1)
        self.assertEqual(stamp, "1000")
        self.assertEqual(len(digest), 64)

    def test_daily_energy_flips_grid_import_and_integrates_minutes(self) -> None:
        samples = []
        for minute in range(60):
            stamp = f"2026-09-24 00:{minute:02d}:00"
            samples.append(stamp)
        data = [
            {"item": "pSystem", "powerData": [{"tp": stamp, "power": 1.0} for stamp in samples]},
            {"item": "pConsum", "powerData": [{"tp": stamp, "power": 2.0} for stamp in samples]},
            {"item": "pGrid", "powerData": [{"tp": stamp, "power": -0.5} for stamp in samples]},
        ]

        day = energy_by_day(data)["2026-09-24"]

        self.assertEqual(day["pv"], 1.0)
        self.assertEqual(day["cons"], 2.0)
        self.assertEqual(day["buy"], 0.5)
        self.assertEqual(day["sell"], 0.0)

    def test_curve_converts_kw_and_sign(self) -> None:
        data = [
            {"item": "pSystem", "powerData": [
                {"tp": "2026-09-24 01:00:00", "power": 1.5},
                {"tp": "2026-09-24 01:01:00", "power": 9},
            ]},
            {"item": "pConsum", "powerData": [{"tp": "2026-09-24 01:00:00", "power": 2.0}]},
            {"item": "pBat", "powerData": [{"tp": "2026-09-24 01:00:00", "power": 0.2}]},
            {"item": "pGrid", "powerData": [{"tp": "2026-09-24 01:00:00", "power": -0.7}]},
            {"item": "soc", "powerData": [{"tp": "2026-09-24 01:00:00", "power": 20}]},
        ]

        points = curve_points(data)

        self.assertEqual(len(points), 1)
        self.assertEqual(points[0]["t"], "01:00")
        self.assertEqual(points[0]["pv"], 1500)
        self.assertEqual(points[0]["load"], 2000)
        self.assertEqual(points[0]["batt"], -200)
        self.assertEqual(points[0]["grid"], 700)
        self.assertEqual(points[0]["soc"], 20)
