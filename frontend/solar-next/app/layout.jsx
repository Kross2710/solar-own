import "./style.css";
import SiteHeader,{SiteFooter} from "./SiteHeader";
import {preferences} from "./i18n/preferences";
import {PreferenceProvider} from "./i18n/context";

export const metadata = { title: "Home Solar" };

export default async function Layout({ children }) {
  const settings=await preferences();
  return <html lang={settings.lang}><body><PreferenceProvider value={settings}>
    <SiteHeader/>{children}<SiteFooter/>
  </PreferenceProvider></body></html>;
}
