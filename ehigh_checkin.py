import hashlib
import os
from dataclasses import dataclass
from typing import Any, ClassVar, Mapping


CHECKIN_URL = "https://app.1hai.cn/SignCenter/UserAssets/SignIn"
USER_AGENT = "%E4%B8%80%E5%97%A8%E7%A7%9F%E8%BD%A6/2904 CFNetwork/3860.700.2 Darwin/25.6.0"


class ConfigError(ValueError):
    """Raised when required replay configuration is missing."""


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

    REQUIRED_ENV: ClassVar[tuple[str, ...]] = (
        "EHI_TOKEN",
        "EHI_APP_IDENTITY",
        "EHI_AUTHORIZATION",
        "EHI_CONTENT_MD5",
        "EHI_NONCESTR",
        "EHI_REQUEST_ROOT_ID",
        "EHI_REQUEST_BODY",
    )

    @classmethod
    def from_env(cls, environment: Mapping[str, str] = os.environ) -> "EhiConfig":
        for name in cls.REQUIRED_ENV:
            if not environment.get(name):
                raise ConfigError(f"缺少环境变量: {name}")

        return cls(
            token=environment["EHI_TOKEN"],
            app_identity=environment["EHI_APP_IDENTITY"],
            authorization=environment["EHI_AUTHORIZATION"],
            content_md5=environment["EHI_CONTENT_MD5"],
            noncestr=environment["EHI_NONCESTR"],
            request_root_id=environment["EHI_REQUEST_ROOT_ID"],
            request_body=environment["EHI_REQUEST_BODY"],
            cookie=environment.get("EHI_COOKIE") or None,
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
    response = session.post(
        CHECKIN_URL,
        headers=_build_headers(config),
        data=config.request_body.encode("utf-8"),
        timeout=(10, 30),
    )
    result = response.json()["Result"]
    return CheckinOutcome(
        status_code=response.status_code,
        result_length=len(result),
        result_sha256=hashlib.sha256(result.encode("utf-8")).hexdigest(),
    )
