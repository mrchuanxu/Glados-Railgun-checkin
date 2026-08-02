import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import checkin
from state_store import StateStore


class FakeAPI:
    checkin_code = checkin.CheckinStatus.SUCCESS
    points = Decimal("500")
    exchange_success = True
    exchange_calls = []

    def __init__(self, domain, cookie_index=0, verbose=False):
        self.domain = domain

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def get_status(self, cookie):
        return "100 天", 0

    def checkin(self, cookie):
        status_text = {
            checkin.CheckinStatus.SUCCESS: "签到成功",
            checkin.CheckinStatus.REPEAT: "重复签到",
            checkin.CheckinStatus.FAILURE: "签到失败",
        }[self.checkin_code]
        return {"status": status_text, "points": "10", "code": self.checkin_code}

    def get_points(self, cookie):
        if self.points is None:
            return "None 积分", None
        return f"{self.points} 积分", self.points

    def exchange(self, cookie, plan):
        self.exchange_calls.append(plan)
        return checkin.ExchangeResult(self.exchange_success, "兑换成功" if self.exchange_success else "兑换失败")


def config(interval=30):
    return SimpleNamespace(
        cookies_list=["secret-cookie"],
        DOMAINS=["glados.cloud"],
        exchange_interval_days=interval,
        verbose=False,
    )


class CheckerTests(unittest.TestCase):
    def setUp(self):
        FakeAPI.checkin_code = checkin.CheckinStatus.SUCCESS
        FakeAPI.points = Decimal("500")
        FakeAPI.exchange_success = True
        FakeAPI.exchange_calls = []

    def make_store(self, directory):
        return StateStore(str(Path(directory) / "state.json"))

    def seed_task(self, store, valid_days, due=False, next_date=None):
        task_id = store.task_id("secret-cookie", "glados.cloud")
        task = store.get_task(task_id, "glados.cloud")
        task["valid_days"] = valid_days
        task["exchange_due"] = due
        task["next_exchange_date"] = next_date
        store.update_task(task_id, task)
        return task_id

    @patch("checkin.API", FakeAPI)
    def test_due_day_selects_plan500_and_resets_after_success(self):
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            task_id = self.seed_task(store, 19)

            checker = checkin.Checker(config(interval=20), store, date(2026, 8, 2))
            checker.checkin_all()

            task = store.get_task(task_id, "glados.cloud")
            self.assertEqual(FakeAPI.exchange_calls, ["plan500"])
            self.assertEqual(task["valid_days"], 0)
            self.assertFalse(task["exchange_due"])
            self.assertEqual(task["last_exchange_success_date"], "2026-08-02")
            self.assertEqual(store.last_complete_date, "2026-08-02")

    @patch("checkin.API", FakeAPI)
    def test_insufficient_points_schedules_retry_and_freezes_count(self):
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            task_id = self.seed_task(store, 29)
            FakeAPI.points = Decimal("74")

            first = checkin.Checker(config(), store, date(2026, 8, 2))
            first.checkin_all()

            task = store.get_task(task_id, "glados.cloud")
            self.assertEqual(task["valid_days"], 30)
            self.assertTrue(task["exchange_due"])
            self.assertEqual(task["next_exchange_date"], "2026-08-07")
            self.assertEqual(FakeAPI.exchange_calls, [])

            second = checkin.Checker(config(), store, date(2026, 8, 3))
            second.checkin_all()
            task = store.get_task(task_id, "glados.cloud")
            self.assertEqual(task["valid_days"], 30)
            self.assertEqual(task["next_exchange_date"], "2026-08-07")

            FakeAPI.points = Decimal("200")
            retry = checkin.Checker(config(), store, date(2026, 8, 7))
            retry.checkin_all()
            task = store.get_task(task_id, "glados.cloud")
            self.assertEqual(FakeAPI.exchange_calls, ["plan200"])
            self.assertEqual(task["valid_days"], 0)
            self.assertFalse(task["exchange_due"])

    @patch("checkin.API", FakeAPI)
    def test_failed_checkin_does_not_increment(self):
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            task_id = self.seed_task(store, 7)
            FakeAPI.checkin_code = checkin.CheckinStatus.FAILURE

            checker = checkin.Checker(config(), store, date(2026, 8, 2))
            checker.checkin_all()

            self.assertEqual(store.get_task(task_id, "glados.cloud")["valid_days"], 7)

    @patch("checkin.API", FakeAPI)
    def test_repeat_checkin_counts_as_valid_day(self):
        with tempfile.TemporaryDirectory() as directory:
            store = self.make_store(directory)
            task_id = self.seed_task(store, 7)
            FakeAPI.checkin_code = checkin.CheckinStatus.REPEAT

            checker = checkin.Checker(config(), store, date(2026, 8, 2))
            checker.checkin_all()

            self.assertEqual(store.get_task(task_id, "glados.cloud")["valid_days"], 8)


if __name__ == "__main__":
    unittest.main()
