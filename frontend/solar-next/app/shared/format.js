export const fmtNum = (value,lang="en") => Number.isFinite(value) ? value.toLocaleString(lang==="vi"?"vi-VN":"en-GB", { maximumFractionDigits: 1 }) : "—";
export const fmtMoney = (value,lang="en",currency="VND") => Number.isFinite(value) ?
  value.toLocaleString(lang==="vi"?"vi-VN":"en-GB",{style:"currency",currency,maximumFractionDigits:0}) : "—";
export const parseDateMonth = (date,lang="en") => new Date(date + "T00:00:00Z").toLocaleDateString(lang==="vi"?"vi-VN":"en-GB", { day:"numeric", month:"short", timeZone:"UTC" });
