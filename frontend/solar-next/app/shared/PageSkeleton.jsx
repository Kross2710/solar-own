"use client";

import {usePreferences} from "../i18n/context";

const chartHeights = [30, 46, 40, 58, 51, 68, 60, 72, 82, 74, 90, 84];

export default function PageSkeleton({title, type}) {
  const {t} = usePreferences();

  return <main className="route-loading" aria-busy="true">
    {title && <div className="heading"><h1>{t(title)}</h1></div>}
    <p className="loading-status" role="status">
      <span className="loading-spinner" aria-hidden="true"/>
      {t("Loading page…")}
    </p>
    <div className={`panel ${type === "overview" ? "skeleton-overview" : ""}`} aria-hidden="true">
      {type === "calendar" && <div className="skeleton-grid">
        {Array.from({length: 35}, (_, day) => <span key={day}/>)}
      </div>}
      {type === "chart" && <div className="skeleton-chart">
        {chartHeights.map((height, month) => <span key={month} style={{height: `${height}%`}}/>)}
      </div>}
    </div>
  </main>;
}
