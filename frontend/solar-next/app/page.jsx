import {pageMetadata} from "./i18n/metadata";
import {preferences} from "./i18n/preferences";
import {translator} from "./i18n/translate";
import {read} from "./shared/read";
import Refresh from "./shared/Refresh";
import Overview from "./overview/Overview";
import Trend from "./overview/Trend";
import {demoReading,demoHistory} from "./overview/demo";
import {demoData} from "./optimization/demo";
import demoMoney from "./money/demo.json";
import {publicReading,selfShare,siteDay} from "./overview/telemetry";
import "./overview/overview.css";

export const dynamic = "force-dynamic";

export default async function Home({searchParams}) {
  const {lang}=await preferences();
  const t=translator(lang);
  const demo = (await searchParams).demo === "1";
  const [metrics,history,daily,forecast,money] = demo ?
    [demoReading,demoHistory,[],demoData[1],demoMoney] :
    await Promise.all(["metrics","history?hours=24","daily?days=31","forecast","money"].map(read));
  const now = demo ? Date.parse(demoReading.timestamp) : Date.now();
  const today = siteDay(now);
  const past = (Array.isArray(daily) ? daily : []).filter(d=>d.day < today && d.day >= siteDay(now-30*86400000))
    .map(d=>selfShare(d.cons,d.buy)).filter(Number.isFinite);
  const days = forecast?.ready ? forecast.days : [];
  return <main className="overview">
    <div className="heading"><h1>{t("Overview")}</h1><span>{demo ? t("Demo data · ") : ""}{new Intl.DateTimeFormat(lang==="vi"?"vi-VN":"en-GB",{
      timeZone:"Asia/Ho_Chi_Minh",day:"numeric",month:"long",year:"numeric"
    }).format(now)}</span></div>
    <Overview initial={publicReading(metrics)} initialTime={now} demo={demo}
      average={past.length ? Math.round(past.reduce((a,b)=>a+b,0)/past.length) : null}
      forecast={days.find(d=>d.date===today)?.kwh} saved={money?.today?.saved}/>
    <Trend samples={Array.isArray(history) ? history : []}/>
    {!demo && <Refresh interval={60000}/>}
  </main>;
}

export const generateMetadata = () => pageMetadata("Overview");
