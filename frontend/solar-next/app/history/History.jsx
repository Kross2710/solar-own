"use client";

import {usePreferences} from "../i18n/context";
import "./history.css";
import Readings from "../shared/Readings";
import { useId, useRef, useState } from "react";
import NavIcon from "../shared/NavIcon";

import {fmtNum} from "../shared/format";
const formatDate = (lang,day, options) => new Intl.DateTimeFormat(lang==="vi"?"vi-VN":"en-GB", { ...options, timeZone: "UTC" }).format(new Date(day + "T00:00:00Z"));

const sources = [
  ["kwh", "Solar", "Solar"],
  ["buy", "Grid bought", "Grid"],
  ["lost_kwh", "Unused solar", "Unused"],
];
const hasEstimate = row => Number.isFinite(row.lost_kwh);
const barWidth = (value, ceiling) => Number.isFinite(value) ? (value / ceiling * 100) + "%" : "0%";
const week = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function Details({ row }) {
  const {t,lang}=usePreferences();
  const value=n=>fmtNum(n,lang);
  const dateLabel=(day,options)=>formatDate(lang,day,options);
  return <aside className="detail">
    <div className="caption">{t("Selected day")}</div>
    <h2>{dateLabel(row.day, { day: "numeric", month: "long" })}</h2>
    <p className="weekday">{dateLabel(row.day, { weekday: "long" })}</p>
    {sources.map(([key, label]) => <section key={key} className={key}>
      <div className="label"><i />{t(label)}</div>
      <strong>{value(row[key])}{Number.isFinite(row[key]) && <> <small>kWh</small></>}</strong>
      {key === "lost_kwh" && <p className="caption">{t(hasEstimate(row)
        ? "Estimated solar energy that could have been generated."
        : "No estimate for this day.")}</p>}
    </section>)}
  </aside>;
}

function MonthPicker({months, month, onChange}) {
  const {t, lang} = usePreferences();
  const dialog = useRef(null);
  const titleId = useId();
  const index = months.indexOf(month);
  const label = (key, options) => formatDate(lang, key + "-01", options);
  const fullLabel = key => label(key, {month: "long", year: "numeric"});
  const years = [...new Set(months.map(key => key.slice(0, 4)))].reverse();

  return <div className="history-month-picker" role="group" aria-label={t("Month")}>
    <button type="button" className="history-month-arrow" aria-label={t("Previous month")}
      disabled={index === 0} onClick={() => onChange(months[index - 1])}>
      <NavIcon name="chevronRight"/>
    </button>
    <button type="button" className="history-month-current" aria-haspopup="dialog"
      onClick={() => dialog.current.showModal()}>
      <span aria-live="polite">{fullLabel(month)}</span>
    </button>
    <button type="button" className="history-month-arrow" aria-label={t("Next month")}
      disabled={index === months.length - 1} onClick={() => onChange(months[index + 1])}>
      <NavIcon name="chevronRight"/>
    </button>

    <dialog ref={dialog} className="history-month-dialog" aria-labelledby={titleId}>
      <div className="history-month-dialog-head">
        <h2 id={titleId}>{t("Choose month")}</h2>
        <form method="dialog">
          <button type="submit" className="history-month-close" aria-label={t("Close")}><span aria-hidden="true">×</span></button>
        </form>
      </div>
      {years.map(year => <div className="history-month-year" key={year}>
        <h3>{year}</h3>
        <div className="history-month-grid">
          {months.filter(key => key.startsWith(year)).map(key =>
            <button type="button" key={key} aria-label={fullLabel(key)} aria-pressed={key === month}
              onClick={() => {onChange(key); dialog.current.close();}}>
              {label(key, {month: "short"})}
            </button>
          )}
        </div>
      </div>)}
    </dialog>
  </div>;
}

export default function History({ rows, demo }) {
  const {t,lang,advanced}=usePreferences();
  const value=n=>fmtNum(n,lang);
  const dateLabel=(day,options)=>formatDate(lang,day,options);
  const months = [...new Set((rows || []).map(row => row.day.slice(0, 7)))].sort();
  const [chosen, setChosen] = useState("");
  const month = months.includes(chosen.slice(0, 7)) ? chosen.slice(0, 7) : months.at(-1);
  const days = (rows || []).filter(row => row.day.startsWith(month)).sort((a,b) => a.day.localeCompare(b.day));
  const selected = days.find(row => row.day === chosen) || days.at(-1);
  const byDate = new Map(days.map(row => [Number(row.day.slice(-2)), row]));
  const peak = Math.max(1, ...days.flatMap(row => sources.map(([key]) => row[key])).filter(Number.isFinite));
  const ceiling = Math.ceil(peak / 10) * 10;
  const start = new Date(month + "-01T00:00:00Z");
  const offset = (start.getUTCDay() + 6) % 7;
  const count = new Date(Date.UTC(start.getUTCFullYear(), start.getUTCMonth()+1, 0)).getUTCDate();

  return <main className="history-page">{demo && <small className="demo-label">{t("Demo data")}</small>}
    <div className="heading">
      <h1>{t("Energy history")}</h1>
      {selected && <MonthPicker months={months} month={month} onChange={key => {
        if (key !== month) setChosen(key + "-00");
      }}/>}
    </div>
    {!selected ? <div className="panel empty"><h2>{rows ? t("No daily readings yet") : t("History is unavailable")}</h2><p>{rows ? t("Daily totals appear here after the first sync.") : t("The history API could not be reached.")}</p><a href="/history">{t("Retry")}</a> · <a href="/history?demo=1">{t("Preview with demo data")}</a></div> : <>
    <div className="totals">{sources.map(([key,label]) => {
      const known = days.map(row => row[key]).filter(Number.isFinite);
      return <div className={key} key={key}><div className="label"><i />{t(label)}</div><strong>{value(known.length ? known.reduce((a,b)=>a+b,0) : null)}{known.length > 0 && <> <small>kWh</small></>}</strong><p>{key === "lost_kwh" && <>{t("Estimate")} · </>}{lang==="vi"?known.length+" ngày có dữ liệu trong tháng":known.length+" recorded days this month"}</p></div>;
    })}</div>
    <div className="layout"><section className="panel calendar"><div className="calhead"><h2>{t("Daily energy")}</h2></div>
    <div className="calendar-grid">{(lang==="vi"?["T2","T3","T4","T5","T6","T7","CN"]:week).map(d => <span className="week" key={d}>{d}</span>)}{Array.from({length:offset},(_,i)=><span key={"offset"+i}/>)}
    {Array.from({length:count},(_,i)=>{const day=i+1,row=byDate.get(day);
      if (!row) return <span className="day missing" key={day} aria-label={day+t(", no reading")}>{day}</span>;
      return <button type="button" key={day} className="day" aria-pressed={selected.day===row.day} aria-label={[row.day, ...sources.map(([key,label]) =>
        t(label) + ": " + (Number.isFinite(row[key]) ? value(row[key]) + " kWh" : t("Unavailable")))].join(", ")} onClick={()=>setChosen(row.day)}>
      <span>{day}</span>{sources.map(([key])=><span key={key} className={"mini "+key+(key === "lost_kwh" && !hasEstimate(row) ? " unestimated" : "")}><b style={{width:barWidth(row[key],ceiling)}}/></span>)}</button>;
    })}</div>
    <div className="calendar-key">
      <div className="calendar-legend">{sources.map(([key,,shortLabel]) =>
        <span key={key} className={"label "+key}><i />{t(shortLabel)}</span>)}</div>
      <p className="scale">{t("Shared scale · 0–")}{value(ceiling)}{t(" kWh per day")}</p>
    </div></section>
    <div aria-live="polite"><Details row={selected}/></div></div>
    <p className="caption missing-estimate-note">{t("Dashed line: no estimate. A recorded zero is shown as 0 kWh.")}</p>
    {advanced && <Readings title={dateLabel(selected.day,{day:"numeric",month:"long"})} rows={[
      [t("Daily consumption"),value(selected.cons)+" kWh"],[t("Battery discharged"),value(selected.batt)+" kWh"]
    ]}/>}
    </>}
  </main>;
}
