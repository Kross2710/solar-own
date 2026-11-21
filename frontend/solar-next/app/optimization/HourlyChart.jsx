"use client";

import {useState} from "react";
import {translator} from "../i18n/translate";
import {fmtNum} from "../shared/format";

const clock = hour => String(hour).padStart(2,"0")+":00";

export default function HourlyChart({hours,peak,lang}) {
  const [choice,setChoice] = useState(null);
  const row = hours.find(r=>r.hour===choice) ?? hours.find(r=>r.hour===peak) ?? hours[0];
  const t = translator(lang);
  const ceiling = Math.max(5,Math.ceil(Math.max(...hours.map(r=>r.pv_kw))/5)*5);
  const label = r => clock(r.hour)+"–"+clock(r.hour+1)+" · "+t("Available PV")+" "+fmtNum(r.pv_kw,lang)+" kW · "+t("Unused solar")+" "+fmtNum(r.unused_kw,lang)+" kW";
  return <figure className="hour-chart">
    <figcaption>{t("Hourly forecast")} <span>kW</span></figcaption>
    <div className="chart-frame">
      <div className="chart-axis" aria-hidden="true"><span>{ceiling}</span><span>{ceiling/2}</span><span>0</span></div>
      <div className="plot">
        {hours.map(r=><button key={r.hour} type="button" aria-label={label(r)} aria-pressed={r.hour===row.hour}
          onFocus={()=>setChoice(r.hour)} onClick={()=>setChoice(r.hour)} onPointerEnter={()=>setChoice(r.hour)}>
          <span className="pv-bar" style={{height:r.pv_kw/ceiling*100+"%"}}/>
          <span className="unused-bar" style={{height:r.unused_kw/ceiling*100+"%"}}/>
        </button>)}
      </div>
    </div>
    <div className="chart-ticks" aria-hidden="true">{[6,9,12,15,18].map(h=><span key={h}>{clock(h)}</span>)}</div>
    <div className="chart-reading"><b>{clock(row.hour)}–{clock(row.hour+1)}</b>
      <span className="pv-key">{t("Available PV")} <b>{fmtNum(row.pv_kw,lang)} kW</b></span>
      <span className="unused-key">{t("Unused solar")} <b>{fmtNum(row.unused_kw,lang)} kW</b></span>
    </div>
  </figure>;
}
