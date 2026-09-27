import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Any, ClassVar, Mapping
from urllib.parse import parse_qsl

import requests


CHECKIN_URL = "https://app.1hai.cn/SignCenter/UserAssets/SignIn"
USER_AGENT = "%E4%B8%80%E5%97%A8%E7%A7%9F%E8%BD%A6/2904 CFNetwork/3860.700.2 Darwin/25.6.0"
logger = logging.getLogger("ehigh_checkin")


class ConfigError(ValueError):
    """Raised when required replay configuration is missing."""


class CheckinError(RuntimeError):
    """Raised when a check-in response cannot be safely accepted."""


@dataclass(frozen=True)
class EhiConfig:
    token: str
    app_identity: str
    authorization: str
    content_md5: str
    noncestr: str
    request_root_id: str
    request_body: str
    cookie: str | None = None

    CONFIG_ENV: ClassVar[str] = "EHI_CONFIG"
    REQUIRED_KEYS: ClassVar[frozenset[str]] = frozenset(
        {
            "token",
            "app_identity",
            "authorization",
            "content_md5",
            "noncestr",
            "request_root_id",
            "request_body",
            "cookie",
        }
    )
    NON_EMPTY_KEYS: ClassVar[frozenset[str]] = REQUIRED_KEYS - {"cookie"}

    @classmethod
    def from_env(cls, environment: Mapping[str, str] = os.environ) -> "EhiConfig":
        encoded = environment.get(cls.CONFIG_ENV)
        if not encoded:
            raise ConfigError(f"缺少环境变量: {cls.CONFIG_ENV}")

        if re.search(r"%(?![0-9A-Fa-f]{2})", encoded):
            raise ConfigError("EHI_CONFIG URL 编码无效")

        try:
            pairs = parse_qsl(
                encoded,
                keep_blank_values=True,
                strict_parsing=True,
                encoding="utf-8",
                errors="strict",
            )
        except (UnicodeDecodeError, ValueError):
            raise ConfigError("EHI_CONFIG URL 编码无效") from None

        values = dict(pairs)

        return cls(
            token=values["token"],
            app_identity=values["app_identity"],
            authorization=values["authorization"],
            content_md5=values["content_md5"],
            noncestr=values["noncestr"],
            request_root_id=values["request_root_id"],
            request_body=values["request_body"],
            cookie=values["cookie"] or None,
        )


@dataclass(frozen=True)
class CheckinOutcome:
    status_code: int
    result_length: int
    result_sha256: str


def _build_headers(config: EhiConfig) -> dict[str, str]:
    headers = {
        "Accept": "*/*",
        "Content-Type": "application/json",
        "Accept-Language": "zh-CN,zh-Hans;q=0.9",
        "AppVersion": "7431",
        "AppPlatform": "iPhone",
        "User-Agent": USER_AGENT,
        "Authorization": config.authorization,
        "ehiContent-MD5": config.content_md5,
        "noncestr": config.noncestr,
        "x-ms-request-root-id": config.request_root_id,
        "Token": config.token,
        "AppIdentity": config.app_identity,
    }
    if config.cookie:
        headers["Cookie"] = config.cookie
    return headers


def perform_checkin(config: EhiConfig, session: Any) -> CheckinOutcome:
    try:
        response = session.post(
            CHECKIN_URL,
            headers=_build_headers(config),
            data=config.request_body.encode("utf-8"),
            timeout=(10, 30),
        )
    except requests.RequestException as error:
        raise CheckinError(f"网络请求失败: {type(error).__name__}") from None

    if not 200 <= response.status_code < 300:
        raise CheckinError(f"HTTP 状态异常: {response.status_code}")

    try:
        payload = response.json()
    except (json.JSONDecodeError, ValueError) as error:
        raise CheckinError("响应不是有效 JSON") from error

    if not isinstance(payload, dict):
        raise CheckinError("响应 JSON 不是对象")

    result = payload.get("Result")
    if not isinstance(result, str) or not result:
        raise CheckinError("响应缺少非空 Result")

    return CheckinOutcome(
        status_code=response.status_code,
        result_length=len(result),
        result_sha256=hashlib.sha256(result.encode("utf-8")).hexdigest(),
    )


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    try:
        config = EhiConfig.from_env()
        with requests.Session() as session:
            outcome = perform_checkin(config, session)
    except (ConfigError, CheckinError) as error:
        logger.error("一嗨签到请求失败: %s", error)
        return 1

    logger.info(
        "一嗨签到请求已被服务端接受: HTTP %s, Result 长度=%s, SHA-256=%s；业务结果仍需 App 验证",
        outcome.status_code,
        outcome.result_length,
        outcome.result_sha256,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
