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

export default async function Optimization({searchParams}) {
  const {lang,advanced}=await preferences();
  const t=translator(lang);
  const fmtNum=value=>formatNumber(value,lang);
  const demo = (await searchParams).demo === "1";
  const [metrics,forecast,hourly,curtailment,money,dayAhead] = demo ? demoData :
    await Promise.all(["metrics","forecast","hourly","curtailment","money","forecast/day-ahead"].map(read));
  const satelliteEstimate = curtailment?.method === "satellite";
  const wastedToday = curtailment?.today?.lost_kwh;
  const wastedTotal = curtailment?.total30_kwh;
  const coveredMinutes = curtailment?.today?.covered_minutes ?? 0;
  const days = forecast?.ready ? forecast.days : [];
  const tomorrow = tomorrowOf(days);
  const kind = dayKind(tomorrow?.qual,tomorrow?.kwh,forecast?.avg30_kwh);
  const plan = batteryPlan(metrics,forecast?.night_need_kwh ?? null);
  const hour = demo ? 12 : Number(new Intl.DateTimeFormat("en-GB",{timeZone:"Asia/Ho_Chi_Minh",hour:"2-digit",hourCycle:"h23"}).format(new Date()));
  const suggestions = buildSuggestions({metrics,kind,hour,tier:money?.projected_tier ?? money?.tier});
  const cells = hourCells(hourly?.hours ?? []);
  const window = bestWindow(cells);
  const hours = dayAhead?.ready ? dayAhead.hours : [];
  const maxYield = Math.max(1,...days.map(d=>d.kwh ?? 0));
  const peak = dayAhead?.peak_hour;
  const energy = value => value == null ? t("Unavailable") : fmtNum(value) + " kWh";
  return <main className="energy-page opt">
    {demo ? <small className="demo-label">{t("Demo data")}</small> : <Refresh interval={forecast?.ready ? 60000 : 30000}/>}
    <div className="heading"><h1>{t("Optimization")}</h1></div>
    {!metrics && !forecast && !hourly && !curtailment && !dayAhead?.ready ? <section>
      <h2>{t("Planning data unavailable")}</h2><a href="/optimization">{t("Retry")}</a> · <a href="?demo=1">{t("Preview demo")}</a>
    </section> : <>
      <section className="solar-plan">
        <div className="plan-lead">
          <h2>{t("Tomorrow’s surplus")}</h2>
          {dayAhead?.ready ? <>
            <p className="surplus-number">{fmtNum(dayAhead.unused_kwh)} <span>kWh</span></p>
            <p className="plan-note">{t("Available PV")} · {energy(dayAhead.pv_kwh)} · {parseDateMonth(dayAhead.date,lang)}</p>
            {peak != null && <p className="peak-time">{t("Peak surplus")} <b>{clock(peak)}–{clock(peak+1)}</b></p>}
            {advanced && <small>{t("Range across past load and battery patterns")} · {fmtNum(dayAhead.scenario_low_kwh)}–{energy(dayAhead.scenario_high_kwh)}</small>}
          </> : <><p>{t("Forecast unavailable.")}</p>{window && <p>{t("Typical solar window · Vietnam time")} · {clock(window.from)}–{clock(window.to)}</p>}</>}
        </div>
        {hours.length > 0 && <HourlyChart hours={hours} peak={peak} lang={lang}/>}
      </section>
      <div className="plan-context"><section className="plan-section"><h2>{t("Today")}</h2><dl>
        {curtailment?.supported && <div><dt>{t(satelliteEstimate ? "Unused solar · satellite estimate" : "Unused solar")}</dt><dd>{energy(wastedToday)}
          {satelliteEstimate && wastedToday != null && coveredMinutes < 720 && <small>{fmtNum(coveredMinutes)} {t("of 720 daylight minutes covered")}</small>}</dd></div>}
        <div><dt>{t("Tonight’s battery")}</dt><dd>{plan?.enough == null ? t("Coverage unknown") : t(plan.enough ? "Enough for a typical night" : "Some grid power needed")}
          {plan && <small>{fmtNum(metrics?.battery_soc)}% · {fmtNum(plan.usableKwh)}{t(" kWh available")}{plan.needKwh != null && " · "+fmtNum(plan.needKwh)+t(" kWh typically needed")}</small>}</dd></div>
      </dl>{suggestions.length>0 && <p className="plan-note">{t(suggestions[0].title)}</p>}</section>
      <section className="plan-section"><h2>{t("Expected generation")}</h2>
        <p className="plan-note">{t("Expected output under typical usage · kWh")}</p>
        {days.length ? <ol className="daily-yield">{days.map(d=><li key={d.date}><small>{d.today ? t("Today") : parseDateMonth(d.date,lang)}</small><span className="yield-column" aria-hidden="true"><i style={{height:(d.kwh ?? 0)/maxYield*100+"%"}}/></span><b>{fmtNum(d.kwh)}</b></li>)}</ol> : <p>{t("Forecast unavailable.")}</p>}
        {advanced && forecast?.quality && <p className="plan-note">{forecast.model} · MAE {energy(forecast.quality.mae)} · RMSE {energy(forecast.quality.rmse)} · {t("Training days")} {forecast.quality.n_train}</p>}
      </section>
      </div>
      {curtailment?.supported && <div className="history-line"><a href="/history">{t("Unused solar history")} ↗</a>
        <span>{energy(wastedTotal)} · {curtailment.days}{t(" recorded days")}</span></div>}
    </>}
  </main>;
}

export const generateMetadata = () => pageMetadata("Optimization");
