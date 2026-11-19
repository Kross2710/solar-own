const icons = {
  Overview: <path d="m3 11 9-8 9 8M5 10v11h5v-7h4v7h5V10"/>,
  History: <><path d="M3 3v18h18"/><path d="M7 16v-4m5 4V7m5 9V4" strokeWidth="2.7"/></>,
  Money: <><ellipse cx="10" cy="6.5" rx="7" ry="3"/><path d="M3 6.5v4c0 1.7 3.1 3 7 3 2.4 0 4.5-.5 5.8-1.2M3 10.5v4c0 1.7 3.1 3 7 3m7-11v3"/><ellipse cx="16" cy="14" rx="5" ry="2.5"/><path d="M11 14v4c0 1.4 2.2 2.5 5 2.5s5-1.1 5-2.5v-4"/></>,
  Optimization: <><path d="M9 18v-1c0-2.5-4-4.1-4-8a7 7 0 1 1 14 0c0 3.9-4 5.5-4 8v1zM10 21h4"/></>,
  Assistant: <><rect x="3" y="7" width="18" height="13" rx="4"/><path d="M12 7V3m-4 9v1m8-1v1m-6 3h4"/></>,
};

export default function NavIcon({name}) {
  return <svg className="nav-icon" aria-hidden="true" viewBox="0 0 24 24" fill="none"
    stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">{icons[name]}</svg>;
}
