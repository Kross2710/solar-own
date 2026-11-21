const hours = Array.from({length:24}, (_, hour) => {
  const pv = Math.round(3500 * Math.max(0, Math.sin((hour - 6) * Math.PI / 12)));
  const load = hour >= 8 && hour < 17 ? 1200 : 800;
  return {hour, pv, load, grid:Math.max(0, load - pv)};
});
const forecastHours = [0.3,1.4,3.2,5.5,7.2,8.1,8.4,7.6,6.1,4.1,2.1,0.5].map((pv_kw,index)=>({
  hour:6+index,
  pv_kw,
  unused_kw:[0,0,0,0.2,1.7,3.8,4.9,4.3,3.2,1.6,0.4,0][index]
}));
const demoDayAhead = {
  ready:true,
  date:"2026-11-20",
  hours:forecastHours,
  peak_hour:12,
  pv_kwh:forecastHours.reduce((total,row)=>total+row.pv_kw,0),
  unused_kwh:forecastHours.reduce((total,row)=>total+row.unused_kw,0),
  scenario_low_kwh:16.2,
  scenario_high_kwh:24.6
};

export const demoData = [
  {battery_soc:96, battery_capacity_kwh:14, pv_power_w:3500, load_power_w:1200},
  {ready:true, model:"Ridge", quality:{mae:2.4,rmse:3.1,n_train:180}, night_need_kwh:8, avg30_kwh:27, days:[27,32,21,30,25].map((kwh,i)=>({
    date:"2026-11-"+(19+i), kwh, today:i===0
  }))},
  {hours, marginal:3126}, {supported:true, today:{lost_kwh:2.4, full_at:"11:40"}, total30_kwh:38, days:30},
  null, demoDayAhead
];
