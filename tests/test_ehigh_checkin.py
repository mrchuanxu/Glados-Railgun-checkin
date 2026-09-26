import hashlib
import unittest
from dataclasses import FrozenInstanceError
from unittest.mock import Mock

from ehigh_checkin import ConfigError, EhiConfig, perform_checkin


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


class EhiRequestTests(unittest.TestCase):
    def setUp(self):
        self.config = EhiConfig.from_env(VALID_ENV)
        self.session = Mock()
        self.response = Mock(status_code=200)
        self.response.json.return_value = {"Result": "encrypted-response"}
        self.session.post.return_value = self.response

    def test_posts_original_body_and_protocol_headers_without_cookie(self):
        perform_checkin(self.config, self.session)

        self.session.post.assert_called_once_with(
            "https://app.1hai.cn/SignCenter/UserAssets/SignIn",
            headers={
                "Accept": "*/*",
                "Content-Type": "application/json",
                "Accept-Language": "zh-CN,zh-Hans;q=0.9",
                "AppVersion": "7431",
                "AppPlatform": "iPhone",
                "User-Agent": "%E4%B8%80%E5%97%A8%E7%A7%9F%E8%BD%A6/2904 CFNetwork/3860.700.2 Darwin/25.6.0",
                "Authorization": "fake-authorization",
                "ehiContent-MD5": "fake-content-md5",
                "noncestr": "fake-nonce",
                "x-ms-request-root-id": "fake-root-id",
                "Token": "fake-token",
                "AppIdentity": "fake-app-identity",
            },
            data=b"fake$request/body*",
            timeout=(10, 30),
        )

    def test_adds_cookie_only_when_configured(self):
        config = EhiConfig.from_env({**VALID_ENV, "EHI_COOKIE": "session=fake-cookie"})

        perform_checkin(config, self.session)

        headers = self.session.post.call_args.kwargs["headers"]
        self.assertEqual(headers["Cookie"], "session=fake-cookie")

    def test_returns_frozen_safe_metadata_for_accepted_response(self):
        outcome = perform_checkin(self.config, self.session)

        self.assertEqual(outcome.status_code, 200)
        self.assertEqual(outcome.result_length, len("encrypted-response"))
        self.assertEqual(
            outcome.result_sha256,
            hashlib.sha256(b"encrypted-response").hexdigest(),
        )
        self.assertFalse(hasattr(outcome, "result"))
        with self.assertRaises(FrozenInstanceError):
            outcome.status_code = 201


if __name__ == "__main__":
    unittest.main()
