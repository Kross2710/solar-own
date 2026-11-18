"""Construct data providers from application configuration."""

from __future__ import annotations

from typing import Any

from providers.base import Provider


def build_provider(
    config: dict[str, Any],
    source: str | None = None,
) -> Provider:
    provider_source = source or config.get("source", "mock")

    if provider_source == "cloud":
        from providers.cloud_goodwe import CloudGoodWeProvider

        cloud = config.get("cloud", {})
        return CloudGoodWeProvider(
            account=cloud.get("account", ""),
            password=cloud.get("password", ""),
            region=cloud.get("region", "auto"),
            station_id=cloud.get("station_id") or None,
            station_name=config.get("station_name"),
            capacity_kw=config.get("capacity_kw"),
            min_refresh_s=int(cloud.get("min_refresh_seconds", 60)),
            price_per_kwh=config.get("price_per_kwh"),
            currency=config.get("currency"),
            battery_reserve_percent=float(
                config.get("battery_reserve_percent", 20)
            ),
        )

    if provider_source == "local":
        from providers.local_goodwe import LocalGoodWeProvider

        local = config.get("local", {})
        return LocalGoodWeProvider(
            host=local.get("host", ""),
            port=int(local.get("port", 502)),
            station_name=config.get("station_name"),
            capacity_kw=config.get("capacity_kw"),
            battery_capacity_kwh=local.get("battery_capacity_kwh")
            or config.get("battery_capacity_kwh"),
            battery_reserve_percent=float(
                config.get("battery_reserve_percent", 20)
            ),
            battery_install_date=local.get("battery_install_date"),
            lat=local.get("lat"),
            lon=local.get("lon"),
        )

    from providers.mock import MockProvider

    return MockProvider(
        station_name=config.get("station_name") or "Nhà mình (giả lập)",
        capacity_kw=float(config.get("capacity_kw", 5.0)),
    )
