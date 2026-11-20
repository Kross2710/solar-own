"use client";
import {usePathname,useSearchParams} from "next/navigation";
import NavIcon from "./shared/NavIcon";
import {useSectionTransition} from "./shared/useSectionTransition";
import Link from "next/link";
import {usePreferences} from "./i18n/context";
const pages=[["/","Overview"],["/history","History"],["/money","Money"],["/optimization","Optimization"],["/assistant","Assistant"]];

export default function SiteHeader() {
  const path=usePathname(),demo=useSearchParams().get("demo")==="1";
  const {t}=usePreferences();
  const navigate=useSectionTransition(path,pages);
  const suffix=demo?"?demo=1":"";
  return <header className="rc-header"><div className="rc-bar">
    <Link href={"/"+suffix} className="brand"><span className="sunmark" aria-hidden="true">☀</span>Home Solar</Link>
    <nav aria-label={t("Main navigation")}>{pages.map(([url,title])=><Link key={url} href={url+suffix} onNavigate={event=>navigate(event,url,suffix)} aria-current={url===path?"page":undefined}><NavIcon name={title}/><span>{t(title)}</span></Link>)}</nav>
    <Link className="prefs-link" aria-current={path==="/settings"?"page":undefined} href={"/settings"+suffix}><span aria-hidden="true">⚙</span> {t("Settings")}</Link>
  </div></header>;
}
export function SiteFooter() {
  const {t}=usePreferences();
  const path=usePathname();
  const suffix=useSearchParams().get("demo")==="1"?"?demo=1":"";
  return <footer className="rc-footer"><div><b>Home Solar</b><small>RC 1</small></div>
    {suffix && <Link href={path}>{t("Exit demo")}</Link>}<span>{t("Site time")} · UTC+7</span><Link href={"/settings"+suffix}>{t("Settings")}</Link></footer>;
}
