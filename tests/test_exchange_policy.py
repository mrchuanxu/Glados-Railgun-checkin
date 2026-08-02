import unittest
from datetime import date
from decimal import Decimal

from exchange_policy import (
    record_checkin,
    reset_after_exchange,
    schedule_retry,
    select_exchange_plan,
    should_attempt_exchange,
)


def task_state(valid_days=0, exchange_due=False, next_exchange_date=None):
    return {
        "valid_days": valid_days,
        "exchange_due": exchange_due,
        "next_exchange_date": next_exchange_date,
        "last_exchange_success_date": None,
    }


class ExchangePolicyTests(unittest.TestCase):
    def test_selects_highest_affordable_plan_at_boundaries(self):
        cases = (
            ("99.99", None),
            ("100", "plan100"),
            ("199.99", "plan100"),
            ("200", "plan200"),
            ("499.99", "plan200"),
            ("500", "plan500"),
            ("900", "plan500"),
        )
        for raw_points, expected in cases:
            with self.subTest(points=raw_points):
                self.assertEqual(select_exchange_plan(Decimal(raw_points)), expected)

    def test_only_valid_checkins_increment_and_due_count_is_frozen(self):
        task = task_state(valid_days=19)
        record_checkin(task, False, 20)
        self.assertEqual(task["valid_days"], 19)

        record_checkin(task, True, 20)
        self.assertEqual(task["valid_days"], 20)
        self.assertTrue(task["exchange_due"])

        record_checkin(task, True, 20)
        self.assertEqual(task["valid_days"], 20)

    def test_all_supported_intervals_become_due_on_final_day(self):
        for interval in (20, 30, 50):
            with self.subTest(interval=interval):
                task = task_state(valid_days=interval - 1)
                record_checkin(task, True, interval)
                self.assertEqual(task["valid_days"], interval)
                self.assertTrue(task["exchange_due"])

    def test_retry_waits_five_calendar_days(self):
        task = task_state(valid_days=30, exchange_due=True)
        today = date(2026, 8, 2)
        schedule_retry(task, today)

        self.assertEqual(task["next_exchange_date"], "2026-08-07")
        self.assertFalse(should_attempt_exchange(task, date(2026, 8, 6)))
        self.assertTrue(should_attempt_exchange(task, date(2026, 8, 7)))

    def test_success_resets_cycle(self):
        task = task_state(valid_days=30, exchange_due=True, next_exchange_date="2026-08-07")
        reset_after_exchange(task, date(2026, 8, 7))

        self.assertEqual(task["valid_days"], 0)
        self.assertFalse(task["exchange_due"])
        self.assertIsNone(task["next_exchange_date"])
        self.assertEqual(task["last_exchange_success_date"], "2026-08-07")


if __name__ == "__main__":
    unittest.main()
