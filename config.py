from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(slots=True, kw_only=True)
class Config:
    service_url: str
    service_port: int
    tg_api_token: str
    secret_token: str


def create_config(env: Mapping[str, str]) -> Config:
    return Config(
        service_url=str(env.get("CYCLIC_URL")),
        service_port=int(env.get("PORT", "3000")),
        tg_api_token=str(env.get("TG_API_TOKEN")),
        secret_token=str(env.get("TG_SECRET_TOKEN")),
    )
