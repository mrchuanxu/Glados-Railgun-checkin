import unittest
from dataclasses import FrozenInstanceError

from ehigh_checkin import ConfigError, EhiConfig


VALID_ENV = {
    "EHI_TOKEN": "fake-token",
    "EHI_APP_IDENTITY": "fake-app-identity",
    "EHI_AUTHORIZATION": "fake-authorization",
    "EHI_CONTENT_MD5": "fake-content-md5",
    "EHI_NONCESTR": "fake-nonce",
    "EHI_REQUEST_ROOT_ID": "fake-root-id",
    "EHI_REQUEST_BODY": "fake$request/body*",
}


class EhiConfigTests(unittest.TestCase):
    def test_loads_required_values_and_omits_optional_cookie(self):
        config = EhiConfig.from_env(VALID_ENV)

        self.assertEqual(config.token, "fake-token")
        self.assertEqual(config.app_identity, "fake-app-identity")
        self.assertEqual(config.authorization, "fake-authorization")
        self.assertEqual(config.content_md5, "fake-content-md5")
        self.assertEqual(config.noncestr, "fake-nonce")
        self.assertEqual(config.request_root_id, "fake-root-id")
        self.assertEqual(config.request_body, "fake$request/body*")
        self.assertIsNone(config.cookie)

    def test_preserves_optional_cookie_verbatim(self):
        environment = {**VALID_ENV, "EHI_COOKIE": "  session=fake; device=test  "}

        self.assertEqual(
            EhiConfig.from_env(environment).cookie,
            "  session=fake; device=test  ",
        )

    def test_empty_optional_cookie_maps_to_none(self):
        environment = {**VALID_ENV, "EHI_COOKIE": ""}

        self.assertIsNone(EhiConfig.from_env(environment).cookie)

    def test_preserves_required_values_verbatim(self):
        environment = {**VALID_ENV, "EHI_REQUEST_BODY": "  fake body  "}

        self.assertEqual(EhiConfig.from_env(environment).request_body, "  fake body  ")

    def test_each_missing_or_empty_required_value_fails_with_name_only(self):
        for name in EhiConfig.REQUIRED_ENV:
            for case in ("missing", "empty"):
                with self.subTest(name=name, case=case):
                    environment = dict(VALID_ENV)
                    if case == "missing":
                        del environment[name]
                    else:
                        environment[name] = ""

                    with self.assertRaises(ConfigError) as context:
                        EhiConfig.from_env(environment)

                    self.assertEqual(str(context.exception), f"缺少环境变量: {name}")
                    self.assertNotIn("fake-", str(context.exception))

    def test_configuration_is_frozen(self):
        config = EhiConfig.from_env(VALID_ENV)

        with self.assertRaises(FrozenInstanceError):
            config.token = "replacement"


if __name__ == "__main__":
    unittest.main()
