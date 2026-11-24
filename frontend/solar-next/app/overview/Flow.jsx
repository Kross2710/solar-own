import {useEffect,useRef,useState} from "react";
import {usePreferences} from "../i18n/context";
import {power} from "./telemetry";
import {fmtNum as formatNumber} from "../shared/format";

const branches = [
  {key:"solar", label:"Solar", metric:"pv_power_w", intoBus:1, side:1},
  {key:"home", label:"Home", metric:"load_power_w", intoBus:-1, side:-1},
  {key:"battery", label:"Battery", metric:"battery_power_w", intoBus:-1, side:1},
  {key:"grid", label:"Grid", metric:"grid_power_w", intoBus:1, side:-1}
];

function wireGeometry(map) {
  const hub=map.querySelector(".hub");
  return branches.map(branch=>{
    const {key,side}=branch;
    const terminal=map.querySelector(".terminal."+key);
    const x=terminal.offsetLeft+side*terminal.offsetWidth/2;
    const y=terminal.offsetTop;
    const endX=hub.offsetLeft-side*hub.offsetWidth/2;
    const endY=hub.offsetTop;
    const turnX=(x+endX)/2;
    const vertical=Math.sign(endY-y);
    const radius=Math.min(12,Math.abs(endX-x)/4,Math.abs(endY-y)/3);
    const path=[
      "M",x,y,"H",turnX-side*radius,
      "Q",turnX,y,turnX,y+vertical*radius,
      "V",endY-vertical*radius,
      "Q",turnX,endY,turnX+side*radius,endY,
      "H",endX
    ].join(" ");
    return {...branch,path,x:turnX,y:(y+endY)/2,angle:vertical*90};
  });
}

function Wires({map,data,animate}) {
  const [geometry,setGeometry]=useState([]);
  useEffect(()=>{
    const element=map.current;
    const update=()=>setGeometry(wireGeometry(element));
    update();
    const observer=new ResizeObserver(update);
    observer.observe(element);
    return ()=>observer.disconnect();
  },[map]);

  return <svg className="wires" aria-hidden="true">
    {geometry.map(({key,metric,intoBus,path,x,y,angle})=>{
      const flow=data?.[metric]*intoBus;
      const active=Number.isFinite(flow) && Math.abs(flow)>=20;
      const rotation=angle+(flow<0?180:0);
      return <g className={key} key={key}>
        <path d={path} className="wire"/>
        {active && <><path className={"conductor "+(animate?"moving":"")} d={path} style={{animationDirection:flow>0?"normal":"reverse"}}/>
        <path className="arrow" d="M-4 -4 L0 0 -4 4" transform={"translate("+x+" "+y+") rotate("+rotation+")"}/></>}
      </g>;
    })}
  </svg>;
}

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

export default function Flow({data,animate,status,age,stamp}) {
  const {t,lang}=usePreferences();
  const fmtNum=value=>formatNumber(value,lang);
  const map=useRef(null);
  const soc = data?.battery_soc;
  const hasCharge = Number.isFinite(soc) && soc >= 0 && soc <= 100;
  return <section className="panel flow-panel"><div className="ov-head"><h2>{t("Power flow")}</h2>
    <div className={"reading-state "+(animate?"active":"")} role="status">
      <span>{t(status)}</span>{age && <span>{age}</span>}
    </div></div>
    <div className="flow-map" ref={map}>
      <Wires map={map} data={data} animate={animate}/>
      <div className="hub" aria-label={t("Inverter")}><Icon name="inverter"/></div>
      {branches.map(({key,label,metric})=><div className={"terminal "+key} key={key}>
        <div className="device"><Icon name={key}/><span>{t(label)}</span></div>
        {key === "battery" && hasCharge ? <>
          <b className="battery-charge">{fmtNum(soc)}%</b>
          <div className="battery-level" aria-hidden="true"><span style={{width: `${soc}%`}}/></div>
          <small className="battery-flow">
            <span>{power(data?.[metric],lang)}</span>
            <span>{t(direction(key,data?.[metric]))}</span>
          </small>
        </> : <>
          <b>{power(data?.[metric],lang)}</b>
          <small>{t(direction(key,data?.[metric]))}</small>
        </>}
      </div>)}
    </div>
    <div className="flow-foot"><span>{t("Inverter reading")}</span><time>{t(stamp)}</time></div>
  </section>;
}
