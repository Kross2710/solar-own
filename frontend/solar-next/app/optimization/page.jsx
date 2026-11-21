import {pageMetadata} from "../i18n/metadata";
import {preferences} from "../i18n/preferences";
import {translator} from "../i18n/translate";
import "./optimization.css";
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
  const maxPower = Math.max(1, ...hours.map(row => row.pv_kw));
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
            <p className="plan-note">{t("Expected unused solar")} · {parseDateMonth(dayAhead.date,lang)}</p>
            <dl>
              {peak != null && <div><dt>{t("Peak surplus")}</dt><dd>{clock(peak)}–{clock(peak+1)}</dd></div>}
              <div><dt>{t("Available PV from 06:00 to 18:00")}</dt><dd>{energy(dayAhead.pv_kwh)}</dd></div>
              <div><dt>{t("Range across past load and battery patterns")}</dt><dd>{fmtNum(dayAhead.scenario_low_kwh)}–{energy(dayAhead.scenario_high_kwh)}</dd></div>
            </dl>
          </> : <><p>{t("Forecast unavailable.")}</p>{window && <p>{t("Typical solar window · Vietnam time")} · {clock(window.from)}–{clock(window.to)}</p>}</>}
        </div>
        {hours.length > 0 && <div className="plan-hours">
          <h3>{t("Hourly forecast")}</h3>
          <table><thead><tr><th scope="col">{t("Hour")}</th><th scope="col">{t("Available PV")} (kW)</th><th scope="col">{t("Unused solar")} (kW)</th></tr></thead>
            <tbody>{hours.map(row=><tr key={row.hour} className={row.hour === peak ? "peak" : undefined}>
              <th scope="row">{clock(row.hour)}</th><td>{fmtNum(row.pv_kw)}</td>
              <td><span className="power-track" aria-hidden="true"><i style={{width:100*row.unused_kw/maxPower+"%"}}/></span>{fmtNum(row.unused_kw)}</td>
            </tr>)}</tbody>
          </table>
        </div>}
      </section>
      <section className="plan-section"><h2>{t("Today")}</h2><dl>
        {curtailment?.supported && <div><dt>{t(satelliteEstimate ? "Unused solar · satellite estimate" : "Unused solar")}</dt><dd>{energy(wastedToday)}
          {satelliteEstimate && wastedToday != null && coveredMinutes < 720 && <small>{fmtNum(coveredMinutes)} {t("of 720 daylight minutes covered")}</small>}</dd></div>}
        <div><dt>{t("Tonight’s battery")}</dt><dd>{plan?.enough == null ? t("Coverage unknown") : t(plan.enough ? "Enough for a typical night" : "Some grid power needed")}
          {plan && <small>{fmtNum(metrics?.battery_soc)}% · {fmtNum(plan.usableKwh)}{t(" kWh available")}{plan.needKwh != null && " · "+fmtNum(plan.needKwh)+t(" kWh typically needed")}</small>}</dd></div>
      </dl>{suggestions.length>0 && <ul>{suggestions.map(s=><li key={s.id}>{t(s.title)}</li>)}</ul>}</section>
      <section className="plan-section"><h2>{t("Expected generation")}</h2>
        <p className="plan-note">{t("Expected output under typical usage · kWh")}</p>
        {days.length ? <ol className="daily-yield">{days.map(d=><li key={d.date}><small>{d.today ? t("Today") : parseDateMonth(d.date,lang)}</small><b>{fmtNum(d.kwh)}</b></li>)}</ol> : <p>{t("Forecast unavailable.")}</p>}
        {advanced && forecast?.quality && <p className="plan-note">{forecast.model} · MAE {energy(forecast.quality.mae)} · RMSE {energy(forecast.quality.rmse)} · {t("Training days")} {forecast.quality.n_train}</p>}
      </section>
      {curtailment?.supported && <section className="plan-section"><h2>{t("Unused solar history")}</h2>
        <dl><div><dt>{t(satelliteEstimate ? "Past 30 completed days" : "Recent total")}</dt><dd>{energy(wastedTotal)}<small>{curtailment.days}{t(" recorded days")}</small></dd></div></dl>
      </section>}
    </>}
  </main>;
}

export const generateMetadata = () => pageMetadata("Optimization");
