import unittest

from checkin import API


class Response:
    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


class APIPointsTests(unittest.TestCase):
    def api_with_payload(self, payload):
        api = API.__new__(API)
        api.POINTS_URL = "/api/user/points"
        api.cookie_index = 1
        api.domain = "glados.cloud"
        api._get_full_url = lambda path: f"https://glados.cloud{path}"
        api._make_request = lambda *args, **kwargs: Response(payload)
        api._log = lambda *args, **kwargs: None
        return api

    def test_parses_decimal_points_without_float_rounding(self):
        api = self.api_with_payload({"code": 0, "points": "500.0000000000000000"})

        text, points = api.get_points("cookie")

        self.assertEqual(text, "500 积分")
        self.assertEqual(str(points), "500.0000000000000000")

    def test_rejects_error_response_and_non_finite_points(self):
        error_api = self.api_with_payload({"code": -1, "points": "500"})
        nan_api = self.api_with_payload({"code": 0, "points": "NaN"})

        self.assertEqual(error_api.get_points("cookie"), ("None 积分", None))
        self.assertEqual(nan_api.get_points("cookie"), ("None 积分", None))


if __name__ == "__main__":
    unittest.main()
