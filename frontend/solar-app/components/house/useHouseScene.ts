import { siteClock } from "@/lib/time";
import { batteryOutlook } from "@/app/optimization/optimization.helpers";
import { useMoney } from "@/hooks/useMoney";
import { useForecast, useHourly } from "@/hooks/useOptimization";
import { energyState, energyStateClass } from "@/lib/energyState";
import { MetricsResponse } from "@/lib/types";
import { HourlyPoint } from "@/lib/types/optimization";
import { SceneData } from "./flow";

// Fallbacks until the system reports its own size and location (Ho Chi Minh City).
const DEFAULT_CAPACITY_KW = 16;
const DEFAULT_LAT = 10.8056;
const DEFAULT_LON = 106.7097;

/** Usual output at this minute, blending the 30-day averages of this hour and the next. */
function typicalAt(hours: HourlyPoint[] | undefined, now: Date): number | null {
  if (!hours) return null;
  const pvOf = (hour: number) => hours.find((point) => point.hour === hour % 24)?.pv ?? null;
  const here = pvOf(siteClock(now).hour);
  const next = pvOf(siteClock(now).hour + 1);
  if (here == null || next == null) return here;
  return here + (next - here) * (siteClock(now).minute / 60);
}

export function useHouseScene(metrics: MetricsResponse): SceneData {
  const { data: forecast } = useForecast();
  const { data: hourly } = useHourly();
  const { money } = useMoney();
  const now = new Date();

  const pvW = metrics.pv_power_w ?? 0;
  const loadW = metrics.load_power_w ?? 0;
  const battW = metrics.battery_power_w ?? 0;
  const gridW = metrics.grid_power_w ?? 0;
  const soc = metrics.battery_soc ?? 0;
  const state = energyState({ pvWatt: pvW, houseWatt: loadW, gridWatt: gridW, battWatt: battW, battSoc: soc });

  const days = forecast?.ready ? forecast.days : [];
  const tier = money?.tier;

  return {
    pvW,
    loadW,
    battW,
    gridW,
    soc,
    capacityKw: metrics.capacity_kw ?? DEFAULT_CAPACITY_KW,
    lat: metrics.lat ?? DEFAULT_LAT,
    lon: metrics.lon ?? DEFAULT_LON,
    now,
    state,
    stateClass: energyStateClass(state),
    typicalPvW: typicalAt(hourly?.hours, now),
    todayKwh: metrics.today_energy_kwh ?? null,
    expectedKwh: days.find((day) => day.today)?.kwh ?? null,
    tomorrowKwh: days.find((day) => !day.today)?.kwh ?? null,
    consKwh: metrics.today_consumption_kwh ?? null,
    buyKwh: metrics.today_buy_kwh ?? null,
    reservePct: metrics.battery_reserve_percent ?? null,
    tier: tier ? { number: tier.index + 1, price: tier.cur_price } : null,
    battery: batteryOutlook(metrics, now),
  };
}
