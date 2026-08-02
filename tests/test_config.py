import os
import unittest
from unittest.mock import patch

from checkin import Config


class ConfigTests(unittest.TestCase):
    def load_with_interval(self, value=None):
        environment = {
            "GLADOS_COOKIES": "cookie",
            "PUSHDEER_SENDKEY": "",
            "GLADOS_VERBOSE": "false",
        }
        if value is not None:
            environment["GLADOS_EXCHANGE_INTERVAL_DAYS"] = value
        with patch.dict(os.environ, environment, clear=True):
            return Config()

    def test_allowed_intervals(self):
        for value in ("20", "30", "50"):
            with self.subTest(value=value):
                self.assertEqual(self.load_with_interval(value).exchange_interval_days, int(value))

    def test_missing_or_invalid_interval_uses_30(self):
        self.assertEqual(self.load_with_interval().exchange_interval_days, 30)
        self.assertEqual(self.load_with_interval("10").exchange_interval_days, 30)
        self.assertEqual(self.load_with_interval("invalid").exchange_interval_days, 30)


if __name__ == "__main__":
    unittest.main()
