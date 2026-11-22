"use client";

import {usePreferences} from "./i18n/context";

export default function Loading() {
  const {t} = usePreferences();
  return <main className="route-loading">
    <p role="status">{t("Loading page…")}</p>
    <div className="panel" aria-hidden="true"/>
  </main>;
}
