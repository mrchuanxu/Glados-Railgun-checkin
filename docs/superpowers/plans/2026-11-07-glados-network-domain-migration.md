# GLaDOS Network Domain Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the default `glados.cloud` target with `glados.network` for check-in, status, points, and exchange requests while preserving `railgun.info` support.

**Architecture:** Keep the existing `Config.DOMAINS` plus relative `APIEndpoint` design. Change only the primary domain value, exercise all four public API methods against that configured domain, and document the state-identity consequence of the domain change.

**Tech Stack:** Python 3.13, standard-library `unittest`, `requests`, Markdown

**Spec:** `docs/superpowers/specs/2026-11-07-glados-network-domain-migration-design.md`

## Global Constraints

- The default domains must be exactly `glados.network` and `railgun.info`, in that order.
- Check-in, status, points, and exchange paths, HTTP methods, cookies, timeouts, response parsing, and error handling must not change.
- Do not add a domain environment variable or hard-code four full endpoint URLs.
- Existing `glados.cloud` state must not be migrated or reused for `glados.network`; `railgun.info` state remains unaffected.

## Review Focus

- A stale `glados.cloud` default would keep sending production traffic to the retired host; `test_default_domains_use_network_and_railgun_only` must reject it.
- Accidentally removing or reordering `railgun.info` would change the existing dual-domain workflow; the exact-list assertion in the same test must pin it.
- A path or HTTP-method regression could break only one of the four operations; `test_primary_domain_builds_all_api_requests` must assert every URL and method.
- Origin or check-in token data could still mention the old host after the target changes; the request-construction test must assert both values use `glados.network`.
- Reusing the old domain's state identifier would corrupt effective-day accounting; `test_domain_change_produces_a_new_task_id` must assert old and new task IDs differ.

---

### Task 1: Migrate the configured GLaDOS domain

**Files:**
- Create: `tests/test_api_urls.py`
- Modify: `tests/test_state_store.py`
- Modify: `checkin.py:131-132`
- Modify: `README.md:162-166`

**Interfaces:**
- Consumes: `Config.DOMAINS`, `API._get_headers() -> Dict[str, str]`, `API._get_checkin_data() -> Dict[str, str]`, and the existing `API.checkin/get_status/get_points/exchange` methods.
- Produces: `Config.DOMAINS == ["glados.network", "railgun.info"]`; the public API methods generate the four `https://glados.network/api/user/...` requests through the existing `_get_full_url()` helper.

- [ ] **Step 1: Add failing default-domain and request-construction tests**

Create `tests/test_api_urls.py` with two `unittest.TestCase` tests:

```python
def test_default_domains_use_network_and_railgun_only(self):
    self.assertEqual(Config.DOMAINS, ["glados.network", "railgun.info"])

def test_primary_domain_builds_all_api_requests(self):
    # Build API via __new__, use Config.DOMAINS[0], and replace _make_request
    # with a recorder returning None so no network request is sent.
    # Invoke checkin, get_status, get_points, and exchange.
    self.assertEqual(recorded_urls, [
        ("https://glados.network/api/user/checkin", "POST"),
        ("https://glados.network/api/user/status", "GET"),
        ("https://glados.network/api/user/points", "GET"),
        ("https://glados.network/api/user/exchange", "POST"),
    ])
    self.assertEqual(api._get_headers()["origin"], "https://glados.network")
    self.assertEqual(api._get_checkin_data(), {"token": "glados.network"})
```

Use the real public API methods and `_get_full_url`; stub only `_make_request` and `_log`. Assert URLs and methods rather than response values.

- [ ] **Step 2: Run the new tests and verify RED**

Run: `python -m unittest tests.test_api_urls -v`

Expected: both tests fail because `Config.DOMAINS[0]` is still `glados.cloud`; failures show the old domain where `glados.network` is expected.

- [ ] **Step 3: Pin domain-based state isolation**

Add `test_domain_change_produces_a_new_task_id` to `tests/test_state_store.py`. Compute task IDs for the same cookie with `glados.cloud` and `glados.network`, then assert they differ. This test records the intentional non-migration behavior and should pass before the production edit.

- [ ] **Step 4: Run the state-isolation test**

Run: `python -m unittest tests.test_state_store.StateStoreTests.test_domain_change_produces_a_new_task_id -v`

Expected: PASS, proving the existing state model already isolates the new domain.

- [ ] **Step 5: Make the minimal production change**

In `checkin.py`, set:

```python
DOMAINS = ["glados.network", "railgun.info"]
```

Do not change `APIEndpoint`, `_get_full_url`, request construction, response handling, or state storage.

- [ ] **Step 6: Verify GREEN for focused tests**

Run: `python -m unittest tests.test_api_urls tests.test_state_store -v`

Expected: PASS for all tests in both modules.

- [ ] **Step 7: Update user-facing documentation**

Add a `2026-11` README changelog entry stating that the primary GLaDOS domain is now `https://glados.network`, all four API operations use it, and `railgun.info` remains supported. Do not claim that old `glados.cloud` state is migrated.

- [ ] **Step 8: Run full verification**

Run: `python -m unittest discover -s tests -v`

Expected: all tests PASS with no failures or errors.

Run: `python -m py_compile checkin.py tests/test_api_urls.py tests/test_state_store.py`

Expected: exit status 0 and no output.

Run: `git diff --check && rg -n 'glados\.cloud' checkin.py README.md tests/test_api_urls.py`

Expected: `git diff --check` succeeds and `rg` produces no matches in runtime configuration, user-facing documentation, or the new request tests.

- [ ] **Step 9: Commit the migration**

```bash
git add checkin.py README.md tests/test_api_urls.py tests/test_state_store.py
git commit -m "fix: migrate glados requests to network domain"
```
