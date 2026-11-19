import {demoData} from "../optimization/demo";
export const demoReading = {
  ...demoData[0], source:"mock", timestamp:"2026-11-19T12:00:00+07:00",status:"online", grid_power_w:0,
  battery_power_w:2300, today_energy_kwh:18.4, today_consumption_kwh:12.6,
  today_buy_kwh:2.8, capacity_kw:6
};
const end = Date.parse(demoReading.timestamp);
export const demoHistory = Array.from({length:289}, (_,index) => {
  const hour = (12 + index / 12) % 24;
  const daylight = Math.max(0, Math.sin((hour - 6) * Math.PI / 12));
  return {
    ts:new Date(end - (288-index)*300000).toISOString(),
    pv:Math.round(daylight*3500*(0.91+0.09*Math.cos(index*Math.PI/12))),
    load:Math.round(1150+220*Math.sin(index/7)+1250*Math.exp(-((hour-19)**2)/2)),
    soc:Math.min(100,Math.round(60+36*Math.cos((hour-12)*Math.PI/14)))
  };
});
Object.assign(demoHistory.at(-1),{load:demoReading.load_power_w,pv:demoReading.pv_power_w,soc:demoReading.battery_soc});
