import {pageMetadata} from "../i18n/metadata";
import {preferences} from "../i18n/preferences";
import {translator} from "../i18n/translate";
import Readings from "../shared/Readings";
import {fmtMoney, fmtNum} from "../shared/format";
import example from "./demo.json";
import "./money.css";

export const dynamic = "force-dynamic";


async function readMoney() {
  try {
    const url = new URL("/api/money", process.env.BACKEND_URL || "http://127.0.0.1:8787");
    const response = await fetch(url, { cache: "no-store", signal: AbortSignal.timeout(8000) });
    if (!response.ok) return null;
    const data = await response.json();
    return data?.cycle && data?.tier && data?.total ? data : null;
  } catch {
    return null;
  }
}

function cycleLabel(lang, day, offset = 0) {
  const date = new Date(day + "T00:00:00Z");
  date.setUTCDate(date.getUTCDate() + offset);
  return date.toLocaleDateString(lang==="vi"?"vi-VN":"en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
}

function Tariff({ tier, tariff, money, t, lang }) {
  const format=value=>fmtNum(value,lang);
  return <section className="panel ledger"><h2>{t("Grid tariff")}</h2>
    <p>{t("Tier ")}{tier.index + 1} · {format(tier.level_kwh)}{t(" kWh bought")}</p>
    <table><caption>{t("Price per kWh by tier")}</caption><thead><tr><th>{t("Tier")}</th><th>{t("Up to (kWh)")}</th><th>{t("Price / kWh")}</th></tr></thead>
      <tbody>{tier.bounds.map((bound, index) => <tr className={tier.index === index ? "current-tier" : ""} key={index}>
        <td>{index + 1}{index === tier.index && t(" · Current")}</td><td>{bound ?? t("Unlimited")}</td><td>{money(tier.prices[index])}</td>
      </tr>)}</tbody></table>
    <p>{tier.to_next_kwh == null ? t("Highest tier reached") : format(tier.to_next_kwh) + t(" kWh until the next tier")}</p>
    {tariff && <small>{lang==="vi"?"EVN sinh hoạt · "+tier.count+" bậc":tariff.label}{t(" · Includes ")}{format(tariff.vat * 100)}{t("% VAT")}{tariff.mixed && t(" · Transition cycle estimated by days")}</small>}
  </section>;
}

function Bills({ bill, history, money, t, lang }) {
  const format=value=>fmtNum(value,lang);
  return <section className="panel ledger"><h2>{t("EVN bills")}</h2>
    {bill ? <><p>{t("Latest closed cycle · ")}{bill.cycle}</p><strong>{money(bill.amount)}</strong>
      <small>{Number.isFinite(bill.kwh) && format(bill.kwh) + " kWh"} {bill.paid_date && t(" · Paid ") + cycleLabel(lang,bill.paid_date)}</small>
      {bill.est_reliable && Number.isFinite(bill.diff_pct) && <p>{t("Difference from estimate · ")}{format(bill.diff_pct)}%</p>}</> : <p>{t("No closed bill available.")}</p>}
    {!!history?.length && <details><summary>{t("Billing history (")}{history.length})</summary>
      <dl>{history.slice().reverse().map(item => <div key={item.cycle}><dt>{item.cycle}</dt><dd>{money(item.amount)}</dd></div>)}</dl>
    </details>}
  </section>;
}

function Dashboard({ data, t, lang, advanced }) {
  const format=value=>fmtNum(value,lang);
  const { cycle, today, total, prev_cycle: previous, payback } = data;
  const money = n => fmtMoney(n,lang,data.currency || "VND");
  const withoutSolar = cycle.saved_now + cycle.bill_now;
  const gridShare = withoutSolar > 0 ? Math.min(100, Math.max(0, 100 * cycle.bill_now / withoutSolar)) : 0;
  const canProject = cycle.days_elapsed >= 3 && Number.isFinite(cycle.bill_proj);
  return <>
    <div className="heading"><h1>{t("Money")}</h1><p>{t("Billing cycle · ")}{cycleLabel(lang,cycle.start)} – {cycleLabel(lang,cycle.end, -1)}</p></div>
    <section className="panel statement"><div>
      <p>{t("Solar savings this cycle")}</p><strong className="saved">{money(cycle.saved_now)}</strong>
      <small>{t("Day ")}{cycle.days_elapsed}{t(" of ")}{cycle.days_in_cycle}</small>
    </div><div className="compare">
      <div><span>{t("Estimated grid bill so far")}</span><b>{money(cycle.bill_now)}</b></div>
      <div className="bill-track" aria-hidden="true"><i style={{ width: gridShare + "%" }} /></div>
      <div><span>{t("Estimated bill without solar")}</span><b>{money(withoutSolar)}</b></div>
    </div></section>
    <div className="money-stats">
      <section className="panel"><h2>{t("Saved today")}</h2><strong>{money(today?.saved)}</strong><small>{Number.isFinite(today?.selfuse_kwh) ? format(today.selfuse_kwh) + t(" kWh self-powered") : t("Daily reading unavailable")}</small></section>
      <section className="panel grid-bill"><h2>{t("Projected cycle bill")}</h2><strong>{canProject ? money(cycle.bill_proj) : "—"}</strong>
        <small>{canProject ? (cycle.days_elapsed < 5 ? t("Early estimate") : t("At current pace")) + " · " + format(cycle.proj_buy_kwh) + " kWh" : t("Too early to project")}</small>
        <div className="bill-so-far"><span>{t("Estimated grid bill so far")}</span><b>{money(cycle.bill_now)}</b></div>
      </section>
      <section className="panel total-savings"><h2>{t("Total savings")}</h2><strong>{money(total.saved)}</strong><small>{t("Across ")}{total.months}{t(" recorded months")}</small></section>
    </div>
    <div className="money-columns"><Tariff lang={lang} t={t} tier={data.tier} tariff={data.tariff} money={money}/>
      <div className="money-stack"><Bills lang={lang} t={t} bill={data.evn_bill} history={data.evn_history} money={money}/>
      {previous?.has && <section className="panel ledger"><h2>{t("Previous cycle comparison")}</h2><p>{t("Estimated bill over the first ")}{previous.days}{t(" days")}</p>
        <strong>{money(Math.abs(previous.bill_delta))}</strong><small>{previous.bill_delta === 0 ? t("No change") : previous.bill_delta < 0 ? t("Lower this cycle") : t("Higher this cycle")}</small></section>}</div>
    </div>
    {advanced && data.projected_tier && <Readings title={t("Projected tariff")} rows={[
      [t("Tier"),data.projected_tier.index+1],[t("Price / kWh"),money(data.projected_tier.cur_price)],
      [t("Projected grid purchase"),format(cycle.proj_buy_kwh)+" kWh"]
    ]}/>}
    {payback && <section className="panel ledger payback"><h2>{t("Investment payback")}</h2>
      <p>{money(payback.recovered)}{t(" recovered of ")}{money(payback.invest)} · {format(payback.pct)}%</p>
      <progress max="100" value={Math.min(100, Math.max(0, payback.pct))} aria-label={t("Investment recovered")}/>
      <small>{payback.done ? t("Investment recovered") : money(payback.remaining) + t(" remaining")}{!payback.done && payback.eta && t(" · Estimated payback ") + cycleLabel(lang,payback.eta)}</small>
      {!payback.done && payback.low_confidence && <small>{t("Early estimate based on less than a year of readings.")}</small>}
    </section>}
  </>;
}

export default async function MoneyPage({ searchParams }) {
  const {lang,advanced}=await preferences();
  const t=translator(lang);
  const demo = (await searchParams).demo === "1";
  const data = demo ? example : await readMoney();
  return <main className="money">
    {demo && <small className="demo-label">{t("Demo data")}</small>}
    {data ? <Dashboard data={data} t={t} lang={lang} advanced={advanced}/> : <><div className="heading"><h1>{t("Money")}</h1></div>
      <section className="panel empty"><h2>{t("Billing data unavailable")}</h2><p>{t("The billing API could not provide the current cycle.")}</p>
      <a href="/money">{t("Retry")}</a> · <a href="/money?demo=1">{t("Preview with demo data")}</a></section></>}

  </main>;
}

export const generateMetadata = () => pageMetadata("Money");
