from __future__ import annotations

from typing import Optional # for type hinting of class methods returning self

from .base import Provider, Metrics

class LocalGoodWeProvider(Provider):
    name = "local"
    
    def __init__(self, host: str, port: int = 502, station_name: Optional[str] = None,
                 capacity_kw: Optional[float] = None,
                 battery_capacity_kwh: Optional[float] = None,
                 battery_reserve_percent: Optional[float] = None,
                 battery_install_date: Optional[str] = None,
                 lat: Optional[float] = None, lon: Optional[float] = None):
        self.host = host
        self.port = port
        self.station_name = station_name or "Home Solar"
        self.capacity_kw = capacity_kw
        self.battery_capacity_kwh = battery_capacity_kwh
        self.battery_reserve_percent = battery_reserve_percent
        self.battery_install_date = battery_install_date
        self.lat = lat
        self.lon = lon
        self._inverter = None  # Placeholder for the GoodWe inverter connection
    
    async def _ensure(self):
        """Ensure that the inverter connection is established."""
        if self._inverter is None:
            import goodwe
            self._inverter = await goodwe.connect(self.host, port=self.port, timeout=5, retries=3)
        return self._inverter
    
    async def get_metrics(self) -> Metrics:
        """Fetch metrics from the GoodWe inverter."""
        try:
            inverter = await self._ensure()
            data = await inverter.read_runtime_data()
        except Exception as e:
            self._inverter = None  # Reset connection on failure
            return Metrics(source="local", status="offline", station_name=self.station_name, 
                           error=f"{type(e).__name__}: {str(e)}")
            
        def g(*keys):
            """Lấy giá trị đầu tiên tìm thấy trong data theo danh sách key."""
            for k in keys:
                if k in data and data[k] is not None:
                    return data[k]
            return None
        
        def rw(*keys):
            """Helper function to get a float value."""
            v = g(*keys)
            try:
                return float(v) if v is not None else None
            except (ValueError, TypeError):
                return None
        
        def re(*keys):
            """Round to 1 decimal place for energy values (kWh)."""
            v = g(*keys)
            return round(float(v), 1) if v is not None else None
        
        pv = rw("ppv") or 0.0
        load = rw("house_consumption")
        active = g("active_power") # >0 -> export
        pbatt = g("pbattery1") # < 0 -> charging, > 0 -> discharging
        soc = g("battery_soc")
        
        return Metrics(
            source="local",
            status="online",
            station_name=self.station_name,
            pv_power_w=pv,
            load_power_w=load,
            grid_power_w=None if active is None else -round(float(active)), # buy>0
            battery_power_w=None if pbatt is None else -round(float(pbatt)), # charge>0
            battery_soc=None if soc is None else float(soc),
            today_energy_kwh=re("e_day", "e_today"),
            total_energy_kwh=re("e_total"),
            capacity_kw=self.capacity_kw,
            self_use_rate=None,
            today_buy_kwh=None,
            today_sell_kwh=None,
            today_consumption_kwh=re("e_load_day"),
            meter_total_buy_kwh=re("meter_e_total_imp"),
            meter_total_sell_kwh=re("meter_e_total_exp"),
            battery_capacity_kwh=self.battery_capacity_kwh,
            battery_reserve_percent=self.battery_reserve_percent,
            lat=self.lat,
            lon=self.lon,
        )