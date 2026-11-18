"""Standardized model for all providers to inherit from. 

This is the base class that all providers should extend, 
so frontend can use a consistent interface to fetch metrics, history, and other data.

    grid_power_w: > 0 -> import power from grid
                  < 0 -> export power to grid
    battery_power_w: > 0 -> battery is charging
                    < 0 -> battery is discharging
"""
from __future__ import annotations # for type hinting of class methods returning self

from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from typing import Optional

# Using a fixed timezone (VN - UTC+7) for all datetime objects to avoid timezone issues
VN_TZ = timezone(timedelta(hours=7))

@dataclass
class Metrics:
    source: str = "mock" # mock | cloud | local
    status: str = "online" # online | offline | error
    station_name: Optional[str] = None # Name of the station, if available
    pv_power_w: float = 0.0
    load_power_w: Optional[float] = None
    grid_power_w: Optional[float] = None
    battery_power_w: Optional[float] = None
    battery_soc: Optional[float] = None # State of charge in percentage
    today_energy_kwh: Optional[float] = None
    total_energy_kwh: Optional[float] = None
    today_income: Optional[float] = None
    currency: Optional[str] = None
    capacity_kw: Optional[float] = None
    self_use_rate: Optional[float] = None
    today_buy_kwh: Optional[float] = None
    today_sell_kwh: Optional[float] = None
    today_consumption_kwh: Optional[float] = None
    
    meter_total_buy_kwh: Optional[float] = None
    meter_total_sell_kwh: Optional[float] = None
    month_energy_kwh: Optional[float] = None     # Produced energy this month
    month_income: Optional[float] = None         # Saving this month
    total_income: Optional[float] = None         # Total saving since installation
    battery_capacity_kwh: Optional[float] = None  
    battery_reserve_percent: Optional[float] = None  
    
    lat: Optional[float] = None  # Latitude of the station, if available
    lon: Optional[float] = None # Longitude of the station, if available
    timestamp: str = ""
    error: Optional[str] = None

    def to_dict(self) -> dict:
        if not self.timestamp:
            self.timestamp = datetime.now(VN_TZ).isoformat(timespec="seconds")
        return asdict(self)

class Provider:
    """Base class for all data providers."""
    name = "base"

    async def get_metrics(self) -> Metrics:
        raise NotImplementedError

    async def close(self) -> None:
        pass