"use client";
import {usePathname,useSearchParams} from "next/navigation";
import NavIcon from "./shared/NavIcon";
import Image from "next/image";
import Link, {useLinkStatus} from "next/link";
import {usePreferences} from "./i18n/context";
const pages=[["/","Overview"],["/history","History"],["/money","Money"],["/optimization","Optimization","Optimize"],["/assistant","Assistant"]];

function TabStatus() {
  const {pending} = useLinkStatus();
  return <span hidden data-pending={pending ? "" : undefined}/>;
}

export default function SiteHeader() {
  const path=usePathname(),demo=useSearchParams().get("demo")==="1";
  const {t}=usePreferences();
  const activeTab=pages.findIndex(([url])=>url===path);
  const suffix=demo?"?demo=1":"";
  return <header className="rc-header"><div className="rc-bar">
    <Link href={"/"+suffix} className="brand">
      <Image src="/home-solar-logo.svg" alt="Home Solar" width={152} height={48} unoptimized/>
    </Link>
    <nav aria-label={t("Main navigation")} style={{"--active-tab":activeTab}}>
      {pages.map(([url,title,shortTitle])=>
        <Link key={url} href={url+suffix} aria-current={url===path?"page":undefined}>
          <NavIcon name={title}/>
          <TabStatus/>
          <span className={shortTitle ? "nav-full-label" : undefined}>{t(title)}</span>
          {shortTitle && <span className="nav-short-label">{t(shortTitle)}</span>}
        </Link>
      )}
    </nav>
    <Link className="prefs-link" aria-current={path==="/settings"?"page":undefined} href={"/settings"+suffix}><NavIcon name="settings"/> {t("Settings")}</Link>
  </div></header>;
}
export function SiteFooter() {
  const {t}=usePreferences();
  const path=usePathname();
  const suffix=useSearchParams().get("demo")==="1"?"?demo=1":"";
  return <footer className="rc-footer"><div><b>Home Solar</b><small>RC 1</small></div>
    {suffix && <Link href={path}>{t("Exit demo")}</Link>}<span>{t("Site time")} · UTC+7</span><Link className="footer-settings" href={"/settings"+suffix}>{t("Settings")}</Link></footer>;
}
