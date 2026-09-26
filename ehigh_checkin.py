import os
from dataclasses import dataclass
from typing import ClassVar, Mapping


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
