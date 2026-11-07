import unittest

from checkin import API, Config


class APIURLTests(unittest.TestCase):
    def test_default_domains_use_network_and_railgun_only(self):
        self.assertEqual(Config.DOMAINS, ["glados.network", "railgun.info"])

    def test_primary_domain_builds_all_api_requests(self):
        api = API.__new__(API)
        api.domain = Config.DOMAINS[0]
        api.cookie_index = 1
        api.verbose = False
        api._log = lambda *args, **kwargs: None
        recorded_requests = []

        def record_request(url, method, data=None, cookies=""):
            recorded_requests.append((url, method))
            return None

        api._make_request = record_request

        api.checkin("cookie")
        api.get_status("cookie")
        api.get_points("cookie")
        api.exchange("cookie", "plan200")

        self.assertEqual(
            recorded_requests,
            [
                ("https://glados.network/api/user/checkin", "POST"),
                ("https://glados.network/api/user/status", "GET"),
                ("https://glados.network/api/user/points", "GET"),
                ("https://glados.network/api/user/exchange", "POST"),
            ],
        )
        self.assertEqual(api._get_headers()["origin"], "https://glados.network")
        self.assertEqual(api._get_checkin_data(), {"token": "glados.network"})


if __name__ == "__main__":
    unittest.main()
