import "./assistant.css";
import {pageMetadata} from "../i18n/metadata";
import {preferences} from "../i18n/preferences";
import {translator} from "../i18n/translate";
import {read} from "../shared/read";
import Conversation from "./Conversation";


export default async function Assistant({searchParams}) {
  const {lang}=await preferences();
  const t=translator(lang);
  const demo = (await searchParams).demo === "1";
  const [ai, notices, metrics] = demo ? [
    {enabled:true}, {notices:[{id:1,kind:"night_load_high",data:{night:"2026-11-18",night_kwh:12,avg_kwh:8}}]},
    {battery_soc:96}
  ] : await Promise.all(["ai_status","notices","metrics"].map(read));
  return <main className="assistant-page">
    {demo && <small className="demo-label">{t("Demo data · Sample replies")}</small>}
    <Conversation key={demo ? "demo" : "live"} demo={demo} enabled={ai?.enabled} notices={notices?.notices} soc={metrics?.battery_soc}/>

  </main>;
}

export const generateMetadata = () => pageMetadata("Assistant");
