import {Suspense} from "react";
import {pageMetadata} from "../i18n/metadata";
import {preferences} from "../i18n/preferences";
import {translator} from "../i18n/translate";
import "./optimization.css";
import HourlyChart from "./HourlyChart";
import Refresh from "../shared/Refresh";
import {read} from "../shared/read";
import {fmtNum as formatNumber, parseDateMonth} from "../shared/format";
import {batteryPlan,bestWindow,buildSuggestions,dayKind,hourCells,tomorrowOf} from "./planning";
import {demoData} from "./demo";

const clock = hour => String(hour).padStart(2,"0") + ":00";

function Loading({t}) {
  return <p className="loading-status" role="status"><span className="loading-spinner" aria-hidden="true"/>{t("Loading page…")}</p>;
}

async function ForecastRefresh({forecast}) {
  return <Refresh interval={(await forecast)?.ready ? 60000 : 30000}/>;
}

async function TypicalWindow({hourly,t}) {
  const window = bestWindow(hourCells((await hourly)?.hours ?? []));
  return window && <p>{t("Typical solar window · Vietnam time")} · {clock(window.from)}–{clock(window.to)}</p>;
}

async function TomorrowPlan({dayAhead,hourly,lang,advanced,t,fmtNum,energy}) {
  const prediction = await dayAhead;
  const hours = prediction?.ready ? prediction.hours : [];
  const peak = prediction?.peak_hour;
  return <section className="solar-plan">
    <div className="plan-lead">
      <h2>{t("Tomorrow’s surplus")}</h2>
      {prediction?.ready ? <>
        <p className="surplus-number">{fmtNum(prediction.unused_kwh)} <span>kWh</span></p>
        <p className="plan-note">{t("Available PV")} · {energy(prediction.pv_kwh)} · {parseDateMonth(prediction.date,lang)}</p>
        {peak != null && <p className="peak-time">{t("Peak surplus")} <b>{clock(peak)}–{clock(peak+1)}</b></p>}
        {advanced && <small>{t("Range across past load and battery patterns")} · {fmtNum(prediction.scenario_low_kwh)}–{energy(prediction.scenario_high_kwh)}</small>}
      </> : <><p>{t("Forecast unavailable.")}</p><Suspense fallback={null}><TypicalWindow hourly={hourly} t={t}/></Suspense></>}
    </div>
    {hours.length > 0 && <HourlyChart hours={hours} peak={peak} lang={lang}/>}
  </section>;
}

async function UnusedSolar({curtailment,t,fmtNum,energy}) {
  const summary = await curtailment;
  if (!summary?.supported) return null;
  const satelliteEstimate = summary.method === "satellite";
  const wastedToday = summary.today?.lost_kwh;
  const coveredMinutes = summary.today?.covered_minutes ?? 0;
  return <div><dt>{t(satelliteEstimate ? "Unused solar · satellite estimate" : "Unused solar")}</dt><dd>{energy(wastedToday)}
    {satelliteEstimate && wastedToday != null && coveredMinutes < 720 && <small>{fmtNum(coveredMinutes)} {t("of 720 daylight minutes covered")}</small>}</dd></div>;
}

async function TonightBattery({metrics,forecast,t,fmtNum}) {
  const [reading,prediction] = await Promise.all([metrics,forecast]);
  const plan = batteryPlan(reading,prediction?.night_need_kwh ?? null);
  return <div><dt>{t("Tonight’s battery")}</dt><dd>{plan?.enough == null ? t("Coverage unknown") : t(plan.enough ? "Enough for a typical night" : "Some grid power needed")}
    {plan && <small>{fmtNum(reading?.battery_soc)}% · {fmtNum(plan.usableKwh)}{t(" kWh available")}{plan.needKwh != null && " · "+fmtNum(plan.needKwh)+t(" kWh typically needed")}</small>}</dd></div>;
}

async function Suggestion({metrics,forecast,money,demo,t}) {
  const [reading,prediction,cost] = await Promise.all([metrics,forecast,money]);
  const tomorrow = tomorrowOf(prediction?.ready ? prediction.days : []);
  const kind = dayKind(tomorrow?.qual,tomorrow?.kwh,prediction?.avg30_kwh);
  const hour = demo ? 12 : Number(new Intl.DateTimeFormat("en-GB",{timeZone:"Asia/Ho_Chi_Minh",hour:"2-digit",hourCycle:"h23"}).format(new Date()));
  const [first] = buildSuggestions({metrics:reading,kind,hour,tier:cost?.projected_tier ?? cost?.tier});
  return first && <p className="plan-note">{t(first.title)}</p>;
}

async function ExpectedGeneration({forecast,lang,advanced,t,fmtNum,energy}) {
  const prediction = await forecast;
  const days = prediction?.ready ? prediction.days : [];
  const maxYield = Math.max(1,...days.map(d=>d.kwh ?? 0));
  return <section className="plan-section"><h2>{t("Expected generation")}</h2>
    <p className="plan-note">{t("Expected output under typical usage · kWh")}</p>
    {days.length ? <ol className="daily-yield">{days.map(d=><li key={d.date}><small>{d.today ? t("Today") : parseDateMonth(d.date,lang)}</small><span className="yield-column" aria-hidden="true"><i style={{height:(d.kwh ?? 0)/maxYield*100+"%"}}/></span><b>{fmtNum(d.kwh)}</b></li>)}</ol> : <p>{t("Forecast unavailable.")}</p>}
    {advanced && prediction?.quality && <p className="plan-note">{prediction.model} · MAE {energy(prediction.quality.mae)} · RMSE {energy(prediction.quality.rmse)} · {t("Training days")} {prediction.quality.n_train}</p>}
  </section>;
}

async function UnusedSolarHistory({curtailment,t,energy}) {
  const summary = await curtailment;
  return summary?.supported ? <div className="history-line"><a href="/history">{t("Unused solar history")} ↗</a>
    <span>{energy(summary.total30_kwh)} · {summary.days}{t(" recorded days")}</span></div> : null;
}

async function Planning({metrics,forecast,hourly,curtailment,money,dayAhead,demo,lang,advanced,t}) {
  // Open the panels as soon as any source can provide planning data.
  const sources = [metrics,forecast,hourly,curtailment,Promise.resolve(dayAhead).then(data=>data?.ready)];
  const available = await Promise.any(sources.map(async source => {
    if (!(await source)) throw new Error("Planning data unavailable");
    return true;
  })).catch(()=>false);
  if (!available) return <section>
    <h2>{t("Planning data unavailable")}</h2><a href="/optimization">{t("Retry")}</a> · <a href="?demo=1">{t("Preview demo")}</a>
  </section>;

  const fmtNum = value => formatNumber(value,lang);
  const energy = value => value == null ? t("Unavailable") : fmtNum(value) + " kWh";
  return <>
    <Suspense fallback={<section className="solar-plan"><div className="plan-lead"><h2>{t("Tomorrow’s surplus")}</h2><Loading t={t}/></div></section>}>
      <TomorrowPlan dayAhead={dayAhead} hourly={hourly} lang={lang} advanced={advanced} t={t} fmtNum={fmtNum} energy={energy}/>
    </Suspense>
    <div className="plan-context">
      <section className="plan-section"><h2>{t("Today")}</h2><dl>
        <Suspense fallback={null}><UnusedSolar curtailment={curtailment} t={t} fmtNum={fmtNum} energy={energy}/></Suspense>
        <Suspense fallback={null}><TonightBattery metrics={metrics} forecast={forecast} t={t} fmtNum={fmtNum}/></Suspense>
      </dl><Suspense fallback={null}><Suggestion metrics={metrics} forecast={forecast} money={money} demo={demo} t={t}/></Suspense></section>
      <Suspense fallback={<section className="plan-section"><h2>{t("Expected generation")}</h2><Loading t={t}/></section>}>
        <ExpectedGeneration forecast={forecast} lang={lang} advanced={advanced} t={t} fmtNum={fmtNum} energy={energy}/>
      </Suspense>
    </div>
    <Suspense fallback={null}><UnusedSolarHistory curtailment={curtailment} t={t} energy={energy}/></Suspense>
  </>;
}

export default async function Optimization({searchParams}) {
  const {lang,advanced} = await preferences();
  const t = translator(lang);
  const demo = (await searchParams).demo === "1";
  const [metrics,forecast,hourly,curtailment,money,dayAhead] = demo ? demoData :
    ["metrics","forecast","hourly","curtailment","money","forecast/day-ahead"].map(read);

  return <main className="energy-page opt">
    {demo ? <small className="demo-label">{t("Demo data")}</small> :
      <Suspense fallback={null}><ForecastRefresh forecast={forecast}/></Suspense>}
    <div className="heading"><h1>{t("Optimization")}</h1></div>
    <Suspense fallback={<Loading t={t}/>}>
      <Planning {...{metrics,forecast,hourly,curtailment,money,dayAhead,demo,lang,advanced,t}}/>
    </Suspense>
  </main>;
}

export const generateMetadata = () => pageMetadata("Optimization");
