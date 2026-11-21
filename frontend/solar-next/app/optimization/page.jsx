import {pageMetadata} from "../i18n/metadata";
import {preferences} from "../i18n/preferences";
import {translator} from "../i18n/translate";
import "./optimization.css";
import Readings from "../shared/Readings";
import Refresh from "../shared/Refresh";
import NavIcon from "../shared/NavIcon";
import {read} from "../shared/read";
import {fmtNum as formatNumber, parseDateMonth} from "../shared/format";
import {batteryPlan,bestWindow,buildSuggestions,dayKind,hourCells,tomorrowOf} from "./planning";
import {demoData} from "./demo";

const sourceLabels = {cheap:"Solar", mid:"Battery", dear:"Grid", none:"No data"};
const clock = hour => String(hour).padStart(2,"0") + ":00";

export default async function Optimization({searchParams}) {
  const {lang,advanced}=await preferences();
  const t=translator(lang);
  const fmtNum=value=>formatNumber(value,lang);
  const demo = (await searchParams).demo === "1";
  const [metrics,forecast,hourly,curtailment,money] = demo ? demoData :
    await Promise.all(["metrics","forecast","hourly","curtailment","money"].map(read));
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
  return <main className="energy-page opt">
    {demo ? <small className="demo-label">{t("Demo data")}</small> : <Refresh interval={forecast?.ready ? 60000 : 30000}/>}
    <div className="heading"><h1>{t("Optimization")}</h1></div>
    {!metrics && !forecast && !hourly && !curtailment ? <section className="panel"><h2>{t("Planning data unavailable")}</h2><p><a href="/optimization">{t("Retry")}</a> · <a href="?demo=1">{t("Preview demo")}</a></p></section> : <>
    <section className="panel overnight">
      <div><small><NavIcon name="moon"/>{t(" Tonight’s battery")}</small>
        <h2>{plan?.enough == null ? t("Coverage unknown") : plan.enough ? t("Enough for a typical night") : t("Some grid power needed")}</h2>
        {plan && <span>{fmtNum(plan.usableKwh)}{t(" kWh available")}{plan.needKwh != null && " · "+fmtNum(plan.needKwh)+t(" kWh typically needed")}</span>}
      </div>
      <div className="battery" aria-label={t("Battery charge")}><div style={{width:Math.min(100,Math.max(0,metrics?.battery_soc ?? 0))+"%"}}/><b>{fmtNum(metrics?.battery_soc)}%</b></div>
    </section>
    <div className="energy-columns"><section className="panel"><h2><NavIcon name="clock"/>{t(" Best time for appliances")}</h2>
      <strong className="window">{window ? clock(window.from)+" – "+clock(window.to) : t("No clear window")}</strong>
      <small>{t("Typical solar window · Vietnam time")}</small>
      <ol className="hour-sources" aria-label={t("Typical energy source by hour")}>
        {cells.map(({hour,level})=>{
          const label=clock(hour)+"–"+clock(hour+1)+" · "+t(sourceLabels[level]);
          return <li key={hour} className={"source-"+level} title={label}><span className="hour-label">{label}</span></li>;
        })}
      </ol>
      <div className="ticks" aria-hidden="true"><span>00h</span><span>06h</span><span>12h</span><span>18h</span><span>24h</span></div>
      <div className="source-legend">{Object.entries(sourceLabels).filter(([key])=>cells.some(cell=>cell.level===key)).map(([key,label])=>
        <span key={key}><i className={"source-"+key} aria-hidden="true"/>{t(label)}</span>)}</div>
      {suggestions.length>0 && <details className="actions"><summary>{t("Suggested actions · ")}{suggestions.length}</summary>{suggestions.map(s=><article key={s.id}><b>{t(s.title)}</b><p>{lang==="vi" && s.id==="wash-now" ? "Đang dư "+fmtNum((metrics.pv_power_w-metrics.load_power_w)/1000)+" kW điện mặt trời. Có thể chạy thiết bị ngay." : t(s.detail)}</p></article>)}</details>}
    </section><section className="panel"><h2><NavIcon name="sun"/>{t(" Solar forecast")}</h2><small>{t("Daily generation · kWh")}</small>
      {days.length ? <div className="forecast-bars">{days.map(d=><div key={d.date}><b>{fmtNum(d.kwh)}</b><div className="barwell"><i style={{height:(d.kwh ?? 0)/Math.max(1,...days.map(v=>v.kwh ?? 0))*100+"%"}}/></div><small>{d.today ? t("Today") : parseDateMonth(d.date,lang)}</small></div>)}</div> : <p>{t("Forecast unavailable.")}</p>}
      {advanced && forecast?.quality?.mae != null && <details><summary>{t("Forecast accuracy")}</summary><p>{t("Backtest mean absolute error · ")}{fmtNum(forecast.quality.mae)} kWh</p></details>}
    </section></div>
    {advanced && forecast?.ready && <Readings title={t("Forecast diagnostics")} rows={[
      [t("Model"),forecast.model],[t("Training days"),forecast.quality?.n_train],
      ["MAE",fmtNum(forecast.quality?.mae)+" kWh"],["RMSE",fmtNum(forecast.quality?.rmse)+" kWh"]
    ]}/>}
    {curtailment?.supported && <section className="panel unused">
      <div>
        <h2><NavIcon name="downRight"/>{t(" Unused solar")}</h2>
        <small>{t(satelliteEstimate ? "Satellite estimate today" : "Estimated today")}</small>
      </div>
      <strong>{wastedToday == null ? t("Unavailable") : <>{fmtNum(wastedToday)} <small>kWh</small></>}</strong>
      {satelliteEstimate && wastedToday != null && coveredMinutes < 720 &&
        <small>{fmtNum(coveredMinutes)} {t("of 720 daylight minutes covered")}</small>}
      <details>
        <summary>{t(satelliteEstimate ? "Past 30 completed days" : "Recent total")}</summary>
        <p>{wastedTotal == null ? t("Unavailable") :
          <>{fmtNum(wastedTotal)}{t(" kWh over ")}{curtailment.days}{t(" recorded days")}</>}</p>
      </details>
    </section>}</>}

  </main>;
}

export const generateMetadata = () => pageMetadata("Optimization");
