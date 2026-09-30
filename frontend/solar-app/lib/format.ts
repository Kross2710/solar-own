export const MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function parseDateMonth(dateString: string) {
    const [year, month, day] = dateString.split("-");
    return `${MONTH_NAMES[parseInt(month) - 1]} ${parseInt(day)}`;
}

export function parseDateMonthYear(dateString: string) {
    const [year, month, day] = dateString.split("-");
    return `${MONTH_NAMES[parseInt(month) - 1]} ${parseInt(day)}, ${year}`;
}

const MONEY_LOCALE = "en-US";

function isMissing(v: number | null | undefined): v is null | undefined {
    return v == null || Number.isNaN(v);
}

export function fmtNum(v: number | null | undefined, digits = 0): string {
    if (isMissing(v)) return "—";
    return v.toLocaleString(MONEY_LOCALE, { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

// "1,250,000 đ"
export function fmtMoney(v: number | null | undefined): string {
    if (isMissing(v)) return "—";
    return v.toLocaleString(MONEY_LOCALE, { maximumFractionDigits: 0 }) + " đ";
}

// Headline money: 2,373,777 -> "2.37M", 82,957 -> "83k", below 10k -> fmtMoney
export function fmtMoneyShort(v: number | null | undefined): string {
    if (isMissing(v)) return "—";
    const a = Math.abs(v);
    if (a >= 1_000_000) {
        return (v / 1_000_000).toLocaleString(MONEY_LOCALE, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + "M";
    }
    if (a >= 10_000) return Math.round(v / 1000) + "k";
    return fmtMoney(v);
}

// Rounded to the thousand but kept in full form: 82,957 -> "83,000 đ"
export function fmtMoneyK(v: number | null | undefined): string {
    if (isMissing(v)) return "—";
    return fmtMoney(Math.round(v / 1000) * 1000);
}

export function getPast30Days(dateString: string) {
    const [year, month, day] = dateString.split("-").map(Number);
    const date = new Date(year, month - 1, day);
    date.setDate(date.getDate() - 30);

    const prevYear = date.getFullYear();
    const prevMonth = String(date.getMonth() + 1).padStart(2, "0");
    const prevDay = String(date.getDate()).padStart(2, "0");

    return `${prevYear}-${prevMonth}-${prevDay}` // "2026-09-09"
}