"use client";
import {useRouter} from "next/navigation";
import {useOptimistic,useTransition} from "react";
import PushSettings from "./PushSettings";
import {usePreferences} from "../i18n/context";

export default function Settings() {
  const {t,lang,advanced}=usePreferences();
  const router=useRouter();
  const [pending,startTransition]=useTransition();
  const [shown,setShown]=useOptimistic({lang,advanced},(current,change)=>({...current,...change}));
  function save(key,value) {
    document.cookie=`solar-${key}=${value}; Path=/; Max-Age=31536000; SameSite=Lax`;
    startTransition(()=>{
      setShown(key==="lang" ? {lang:value} : {advanced:value==="1"});
      router.refresh();
    });
  }
  return <main className="prefs"><div className="heading"><h1>{t("Settings")}</h1></div>
    <section className="panel"><div className="pref-row"><label htmlFor="language">{t("Language")}</label>
      <select disabled={pending} id="language" value={shown.lang} onChange={e=>save("lang",e.target.value)}>
        <option value="en">English</option><option value="vi">Tiếng Việt</option></select></div>
      <div className="pref-row"><label htmlFor="advanced">{t("Advanced readings")}<small>{t("Show inverter specifications, daily consumption and forecast diagnostics.")}</small></label>
      <input type="checkbox" role="switch" id="advanced" checked={shown.advanced} disabled={pending} onChange={e=>save("advanced",e.target.checked?"1":"0")}/></div>
    </section><PushSettings/></main>;
}
