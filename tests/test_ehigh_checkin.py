import hashlib
import json
import unittest
from dataclasses import FrozenInstanceError
from unittest.mock import Mock, patch

import requests

from ehigh_checkin import (
    CheckinError,
    ConfigError,
    EhiConfig,
    main,
    perform_checkin,
)


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


class EhiFailureTests(unittest.TestCase):
    def setUp(self):
        self.config = EhiConfig.from_env(VALID_ENV)
        self.session = Mock()
        self.response = Mock(status_code=200)
        self.session.post.return_value = self.response

    def test_rejects_non_2xx_without_parsing_body(self):
        self.response.status_code = 401

        with self.assertRaisesRegex(CheckinError, "HTTP 状态异常: 401"):
            perform_checkin(self.config, self.session)

        self.response.json.assert_not_called()

    def test_wraps_network_exception_without_exception_text(self):
        self.session.post.side_effect = requests.Timeout("fake-token leaked")

        with self.assertRaisesRegex(CheckinError, "网络请求失败: Timeout") as context:
            perform_checkin(self.config, self.session)

        self.assertNotIn("fake-token", str(context.exception))
        self.assertNotIn("leaked", str(context.exception))
        self.assertIsNone(context.exception.__cause__)

    def test_rejects_invalid_json(self):
        self.response.json.side_effect = json.JSONDecodeError("bad", "x", 0)

        with self.assertRaisesRegex(CheckinError, "响应不是有效 JSON"):
            perform_checkin(self.config, self.session)

    def test_rejects_non_object_json(self):
        self.response.json.return_value = ["fake-ciphertext"]

        with self.assertRaisesRegex(CheckinError, "响应 JSON 不是对象"):
            perform_checkin(self.config, self.session)

    def test_rejects_missing_empty_or_non_string_result(self):
        for payload in ({}, {"Result": ""}, {"Result": 123}):
            with self.subTest(payload=payload):
                self.response.json.return_value = payload

                with self.assertRaisesRegex(CheckinError, "响应缺少非空 Result"):
                    perform_checkin(self.config, self.session)


class EhiMainTests(unittest.TestCase):
    @patch("ehigh_checkin.requests.Session")
    def test_success_logs_only_safe_response_metadata(self, session_class):
        ciphertext = "fake-response-ciphertext"
        response = Mock(status_code=200)
        response.json.return_value = {"Result": ciphertext}
        session_class.return_value.__enter__.return_value.post.return_value = response

        with patch.dict("os.environ", VALID_ENV, clear=True):
            with self.assertLogs("ehigh_checkin", level="INFO") as captured:
                exit_code = main()

        output = "\n".join(captured.output)
        self.assertEqual(exit_code, 0)
        self.assertIn("请求已被服务端接受", output)
        self.assertIn("HTTP 200", output)
        self.assertIn(f"Result 长度={len(ciphertext)}", output)
        self.assertIn(hashlib.sha256(ciphertext.encode()).hexdigest(), output)
        self.assertIn("业务结果仍需 App 验证", output)
        for secret in (*VALID_ENV.values(), ciphertext):
            self.assertNotIn(secret, output)
        session_class.return_value.__enter__.assert_called_once_with()
        session_class.return_value.__exit__.assert_called_once_with(None, None, None)

    @patch("ehigh_checkin.requests.Session")
    def test_failure_returns_nonzero_and_logs_sanitized_error(self, session_class):
        session_class.return_value.__enter__.return_value.post.side_effect = (
            requests.Timeout("fake-token leaked")
        )

        with patch.dict("os.environ", VALID_ENV, clear=True):
            with self.assertLogs("ehigh_checkin", level="ERROR") as captured:
                exit_code = main()

        output = "\n".join(captured.output)
        self.assertEqual(exit_code, 1)
        self.assertIn("网络请求失败: Timeout", output)
        self.assertNotIn("leaked", output)
        for secret in VALID_ENV.values():
            self.assertNotIn(secret, output)
        session_class.return_value.__enter__.assert_called_once_with()
        session_class.return_value.__exit__.assert_called_once()


if __name__ == "__main__":
    unittest.main()
