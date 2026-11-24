"use client";
import {usePreferences} from "../i18n/context";
import {useMemo,useState} from "react";
import {power,siteDay,siteTime} from "./telemetry";

const series={
  Power:[["pv","Solar"],["load","Home load"]],
  Battery:[["soc","Battery level"]]
};

// A missing meter reading or a long interruption starts a new line.
function trace(points,key,x,y) {
  let previous=null, path="";
  for (const point of points) {
    if (!Number.isFinite(point[key])) {previous=null;continue;}
    const move=previous==null || point.time-previous>10*60000;
    path+=(move?"M":"L")+x(point.time).toFixed(2)+","+y(point[key]).toFixed(2);
    if (move) path+="l0.01,0";
    previous=point.time;
  }
  return path;
}

export default function Trend({samples}) {
  const {t,lang}=usePreferences();
  const [mode,setMode]=useState("Power"),[picked,setPicked]=useState(null);
  const points=useMemo(()=>samples.map(p=>({...p,time:Date.parse(p.ts)}))
    .filter(p=>Number.isFinite(p.time)).sort((a,b)=>a.time-b.time),[samples]);
  const end=points.at(-1)?.time;
  const start=end-86400000;
  const active=series[mode];
  const available=points.some(p=>active.some(([key])=>Number.isFinite(p[key])));
  const peak=mode==="Battery"?100:Math.max(1000,Math.ceil(points.reduce((max,p)=>
    Math.max(max,p.pv??0,p.load??0),0)/1000)*1000);
  const x=t=>1000*(t-start)/86400000;
  const y=n=>125-120*n/peak;
  const index=Math.max(0,Math.min(picked??points.length-1,points.length-1));
  const point=points[index];
  function inspect(event) {
    const box=event.currentTarget.getBoundingClientRect();
    const time=start+86400000*(event.clientX-box.left)/box.width;
    const closest=points.reduce((best,p,i)=>Math.abs(p.time-time)<Math.abs(points[best].time-time)?i:best,0);
    setPicked(closest);
  }
  return <section className="panel trend"><div className="ov-head"><div><h2>{t("Last 24 hours")}</h2>
    {point && <small>{t("Through ")}{siteDay(end)} · {siteTime(end)} ICT</small>}</div>
    <div className="trend-switch" aria-label={t("Chart view")}>{Object.keys(series).map(item=><button key={item}
      onClick={()=>setMode(item)} aria-pressed={item===mode}>{t(item)}</button>)}</div></div>
    {available ? <>
      <div className="chart-legend">{active.map(([key,label])=><span key={key} className={key}>{t(label)}</span>)}</div>
      <div className="plot"><div className="y-axis">{[1,.5,0].map(frac=><small key={frac}>{mode==="Battery"?peak*frac+"%":power(peak*frac,lang)}</small>)}</div>
        <div className="graph"><svg onPointerDown={inspect} onPointerMove={e=>{if(e.pointerType==="mouse" || e.buttons) inspect(e);}}
          viewBox="0 0 1000 130" preserveAspectRatio="none" role="img" aria-label={t(mode)+t(" trend over 24 hours")}>
          {[5,65,125].map(n=><line key={n} x1="0" x2="1000" y1={n} y2={n}/>)}
          {active.map(([key])=><path className={key} key={key} d={trace(points,key,x,y)}/>)}
          <line className="cursor" x1={x(point.time)} x2={x(point.time)} y1="0" y2="130"/>
        </svg><div className="times">{[0,.25,.5,.75,1].map(f=><small key={f}>{siteTime(start+f*86400000)}</small>)}</div></div>
      </div>
      <div className="sample"><label htmlFor="sample-time">{siteTime(point.time)} ICT</label>
        <input id="sample-time" aria-label={t("Inspect a reading")} type="range" min="0" max={points.length-1} value={index}
          aria-valuetext={siteTime(point.time)} onChange={e=>setPicked(Number(e.target.value))}/>
        <div aria-live="polite">{active.map(([key,label])=><span key={key}>{t(label)} <b>{key==="soc" ? Number.isFinite(point.soc)?point.soc+"%":"—" : power(point[key],lang)}</b></span>)}</div>
      </div>
    </>:<p className="no-samples">{lang==="vi"?"Chưa có số liệu "+t(mode).toLowerCase()+".":"No "+mode.toLowerCase()+" readings available."}</p>}
  </section>;
}
