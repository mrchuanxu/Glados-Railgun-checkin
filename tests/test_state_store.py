import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from state_store import StateStore


class StateStoreTests(unittest.TestCase):
    def test_cookie_and_domain_combinations_have_isolated_ids(self):
        ids = {
            StateStore.task_id("cookie-a", "glados.cloud"),
            StateStore.task_id("cookie-b", "glados.cloud"),
            StateStore.task_id("cookie-a", "railgun.info"),
        }

        self.assertEqual(len(ids), 3)

    def test_round_trip_and_cookie_is_not_stored(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            store = StateStore(str(path))
            cookie = "koa:sess=secret-cookie"
            task_id = store.task_id(cookie, "glados.cloud")
            task = store.get_task(task_id, "glados.cloud")
            task["valid_days"] = 3
            store.update_task(task_id, task)
            store.mark_complete(date(2026, 8, 2))

            restored = StateStore(str(path))
            self.assertEqual(restored.last_complete_date, "2026-08-02")
            self.assertEqual(restored.get_task(task_id, "glados.cloud")["valid_days"], 3)
            self.assertNotIn(cookie, path.read_text(encoding="utf-8"))

    def test_corrupt_state_is_preserved_and_reset(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            path.write_text("not json", encoding="utf-8")

            store = StateStore(str(path))

            self.assertIsNotNone(store.warning)
            self.assertEqual(store.data["tasks"], {})
            self.assertEqual(path.with_name("state.json.corrupt").read_text(), "not json")

    def test_unsupported_version_is_reset(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            path.write_text(json.dumps({"version": 999, "tasks": {}}), encoding="utf-8")

            store = StateStore(str(path))

            self.assertIsNotNone(store.warning)
            self.assertEqual(store.data["version"], 1)


if __name__ == "__main__":
    unittest.main()
