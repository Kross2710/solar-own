import {usePreferences} from "../i18n/context";
import {power} from "./telemetry";
import {fmtNum as formatNumber} from "../shared/format";

const branches = [
  {key:"solar", label:"Solar", metric:"pv_power_w", intoBus:1, path:"M23 26 H40 Q43 26 43 32 V41 Q43 50 50 50", arrow:[37,26,0]},
  {key:"home", label:"Home", metric:"load_power_w", intoBus:-1, path:"M77 26 H60 Q57 26 57 32 V41 Q57 50 50 50", arrow:[63,26,180]},
  {key:"battery", label:"Battery", metric:"battery_power_w", intoBus:-1, path:"M23 74 H40 Q43 74 43 68 V59 Q43 50 50 50", arrow:[37,74,0]},
  {key:"grid", label:"Grid", metric:"grid_power_w", intoBus:1, path:"M77 74 H60 Q57 74 57 68 V59 Q57 50 50 50", arrow:[63,74,180]}
];

function Icon({name}) {
  const paths = {
    solar:<><circle cx="12" cy="12" r="4"/><path d="M12 1v3m0 16v3M1 12h3m16 0h3M4 4l2 2m12 12 2 2M4 20l2-2M18 6l2-2"/></>,
    home:<><path d="M2 11 12 3l10 8M5 10v11h14V10M10 21v-7h4v7"/></>,
    battery:<><rect x="2" y="6" width="18" height="12" rx="3"/><path d="M22 10v4M6 10v4m4-4v4m4-4v4"/></>,
    grid:<><path d="m8 22 4-20 4 20M5 8h14M3 13h18M9 19l6-6m0 6-6-6"/></>,
    inverter:<path d="m14 2-9 12h6l-1 8 9-13h-6z"/>
  };
  return <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">{paths[name]}</svg>;
}

function direction(key, watts) {
  if (!Number.isFinite(watts)) return "No reading";
  if (Math.abs(watts)<20) return "Idle";
  if (key==="battery") return watts>0 ? "Charging" : "Discharging";
  if (key==="grid") return watts>0 ? "Importing" : "Exporting";
  return key==="solar" ? "Generating" : "Consuming";
}

export default function Flow({data,animate,status,stamp}) {
  const {t,lang}=usePreferences();
  const fmtNum=value=>formatNumber(value,lang);
  return <section className="panel flow-panel"><div className="ov-head"><h2>{t("Power flow")}</h2><span className={"reading-state "+(animate?"active":"")}>{t(status)}</span></div>
    <div className="flow-map">
      <svg className="wires" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
        {branches.map(({key,metric,intoBus,path,arrow})=>{
          const flow=data?.[metric]*intoBus;
          const active=Number.isFinite(flow) && Math.abs(flow)>=20;
          const [x,y,angle]=arrow;
          return <g className={key} key={key}><path d={path} className="wire"/>
            {active && <><path className={"conductor "+(animate?"moving":"")} d={path} style={{animationDirection:flow>0?"normal":"reverse"}}/>
            <path className="arrow" d="M-1.25 -1.4 L1.1 0 -1.25 1.4" transform={`translate(${x} ${y}) rotate(${angle+(flow<0?180:0)})`}/></>}
          </g>;
        })}
      </svg>
      <div className="hub" aria-label={t("Inverter")}><Icon name="inverter"/></div>
      {branches.map(({key,label,metric})=><div className={"terminal "+key} key={key}>
        <div className="device"><Icon name={key}/><span>{t(label)}</span></div>
        <b>{power(data?.[metric],lang)}</b>
        <small>{key==="battery" && Number.isFinite(data?.battery_soc) ? fmtNum(data.battery_soc)+"% · " : ""}{t(direction(key,data?.[metric]))}</small>
      </div>)}
    </div>
    <div className="flow-foot"><span>{t("Inverter reading")}</span><time>{t(stamp)}</time></div>
  </section>;
}
