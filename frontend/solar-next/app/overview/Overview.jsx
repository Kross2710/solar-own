"use client";
import {usePreferences} from "../i18n/context";
import {useEffect,useState} from "react";
import {fmtMoney,fmtNum as formatNumber} from "../shared/format";
import {selfShare,siteTime,siteDay} from "./telemetry";
import Readings from "../shared/Readings";
import Flow from "./Flow";
import NavIcon from "../shared/NavIcon";

function useMeter(initial,initialTime,demo) {
  const [state,setState]=useState({data:initial,now:initialTime,connected:Boolean(initial)});
  useEffect(()=>{
    if (demo) return;
    let stopped=false,pending=false;
    const controller=new AbortController();
    async function poll() {
      if (pending || document.hidden) return;
      pending=true;
      try {
        const response=await fetch("/api/overview/metrics",{cache:"no-store",signal:controller.signal});
        if (!response.ok) throw new Error();
        const data=await response.json();
        if (!stopped) setState({data,now:Date.now(),connected:true});
      } catch {
        if (!stopped) setState(prev=>({...prev,now:Date.now(),connected:false}));
      } finally {pending=false;}
    }
    const timer=setInterval(poll,5000);
    document.addEventListener("visibilitychange",poll);
    return ()=>{stopped=true;controller.abort();clearInterval(timer);document.removeEventListener("visibilitychange",poll);};
  },[demo]);
  return state;
}

export default function Overview({initial,initialTime,demo,average,forecast,saved}) {
  const {t,advanced,lang}=usePreferences();
  const fmtNum=value=>formatNumber(value,lang);
  const {data,now,connected}=useMeter(initial,initialTime,demo);
  const time=Date.parse(data?.timestamp);
  const online=data?.status==="online" && !data.hasError;
  const fresh=online && connected && Number.isFinite(time) && Math.abs(now-time)<180000;
  const status=demo || data?.source==="mock" ? "Simulated" : !online ? "Offline" : fresh ? "Live" : "Last reading";
  const stamp=Number.isFinite(time) ? (siteDay(now)!==siteDay(time)?siteDay(time)+" · ":"")+siteTime(time)+" ICT" : "Unavailable";
  const meter=online ? data : null;
  const today=Number.isFinite(time) && siteDay(time)===siteDay(now) ? meter : null;
  const consumed=today?.today_consumption_kwh, bought=today?.today_buy_kwh;
  const share=selfShare(consumed,bought);
  const suffix=demo?"?demo=1":"";
  return <>
    <div className="ov-top"><Flow data={meter} animate={fresh} status={status} stamp={stamp}/>
      <section className="panel day-energy"><div className="ov-head"><h2>{t("Today’s energy")}</h2><a href={"/history"+suffix} aria-label={t("Open energy history")}><NavIcon name="chevronRight"/></a></div>
        <div className="usage-line"><div className="usage-ring" style={{"--share":(share??0)+"%","--rest":share==null?"var(--edge)":"var(--grid)"}}><b>{share==null?"—":share+"%"}</b></div>
          <div><b>{t("Self-powered")}</b><small>{t("Solar + battery")}</small></div></div>
        <dl>{[[t("Solar generated"),today?.today_energy_kwh,"solar"],[t("Home used"),consumed,"home"],[t("Grid bought"),bought,"grid"]].map(([label,n,key])=><div key={key} className={key}><dt>{label}</dt><dd>{fmtNum(n)} <small>kWh</small></dd></div>)}</dl>
        {average!=null && <small>{t("30-day average · ")}{average}{t("% self-powered")}</small>}
      </section></div>
    {advanced && <Readings title={t("Inverter specifications")} rows={[
      [t("PV capacity"),fmtNum(data?.capacity_kw)+" kW"],[t("Battery capacity"),fmtNum(data?.battery_capacity_kwh)+" kWh"],
      [t("Telemetry source"),data?.source],[t("Inverter reading"),stamp]
    ]}/>}
    {!demo && !online && <p className="ov-offline">{t("Live meter unavailable. ")}<a href="/?demo=1">{t("Preview demo")}</a></p>}
    <div className="ov-links">
      <a href={"/optimization"+suffix}><span>{t("Today’s forecast")}</span><b>{fmtNum(forecast)} <small>kWh</small></b><NavIcon name="chevronRight"/></a>
      <a href={"/money"+suffix}><span>{t("Saved today")}</span><b>{fmtMoney(saved)}</b><NavIcon name="chevronRight"/></a>
    </div>
  </>;
}
