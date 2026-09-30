# Home Solar

A home energy dashboard for a hybrid solar system. It shows live power flow, how much of the house load came from solar versus the grid, the EVN bill, and when to shift loads so less sun is wasted.

The UI is a Next.js app in `frontend/solar-app`. A FastAPI service polls the inverter, stores history in SQLite, and serves `/api/*`. In development, Next.js proxies those routes to the API, so a phone on the same LAN can open the site without calling `localhost` on itself.

On startup the API fills missing SEMS history, patches recent sample gaps, rebuilds curtailment, and (when configured) pulls the EVN portal. The same pass runs again every 12 hours. Settings can start a sync by hand.

## Stack

- Next.js 16, React 19, TypeScript, SWR, and Tailwind CSS 4 for the dashboard
- FastAPI and uvicorn for the API
- SQLite (`history.db`) for minute samples, daily totals, EVN bills, notices, and weather
- GoodWe SEMS+ for cloud live data and history
- Optional local Modbus reads through the `goodwe` package
- EVN residential tiered tariff, with VAT, for savings and the projected bill
- Optional yield forecast from Open-Meteo weather plus a walk-forward model (Ridge, or gradient boosting when scikit-learn is installed)
- Optional assistant: Gemini, or a local Ollama model, with function calls against the stored history

`source` in the config selects the live provider: `mock`, `cloud`, or `local`. `history_source` can point history reads at a different provider.

## Screens

| Route | What it shows |
|---|---|
| `/` | Live PV, home load, battery, and grid, plus today's energy split |
| `/history` | Daily generation, month and year totals, self-powered days |
| `/money` | Cycle savings, projected EVN bill, the last real bill, and the current tariff tier |
| `/optimization` | Tonight's battery plan, best hours to run loads, wasted sun, and the next days' yield |
| `/assistant` | Rule-based notices and a streaming chat that can look up history before answering |

The gear in the header opens Settings: text size, battery reserve used by the dashboard estimates (10–80%, written only to `config.json`), manual sync, CSV export of daily history, and system status. Text size is stored in the browser.

A warning notice puts a dot on the Assistant tab. Notices cover an inverter offline for 30 minutes, a night load well above the recent average, a projected bill well above the last real bill, an expensive tier coming this cycle, and a week of wasted sun that jumped versus the week before. They expire on their own and can be dismissed.

## Run it

Use Python 3.12+ and Node 20+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install fastapi uvicorn httpx goodwe

cd frontend/solar-app
npm install
```

The yield forecast also needs `numpy`. Install `scikit-learn` as well if you want the gradient-boosting candidate in the model bake-off. Without `numpy`, the rest of the dashboard still runs and the forecast stays off.

Create `config.json` in the project root. Start with mock data, which needs no accounts:

```json
{
  "source": "mock",
  "history_source": "mock",
  "station_name": "Home Solar",
  "capacity_kw": 16.0,
  "battery_reserve_percent": 20,
  "price_per_kwh": 2500,
  "currency": "VND",
  "poll_interval_seconds": 5,
  "backfill_months": 18,
  "host": "127.0.0.1",
  "port": 8787
}
```

`config.json` and `history.db` are gitignored. Do not commit inverter passwords, portal logins, or API keys.

From the project root:

```bash
source .venv/bin/activate
python server.py
```

In another terminal:

```bash
cd frontend/solar-app
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). The API listens on [http://127.0.0.1:8787](http://127.0.0.1:8787). Next.js rewrites `/api/*` to that process, with a 120 second proxy timeout so a long assistant reply is not cut off. Override the target with `BACKEND_URL` if the API is not on port 8787.

To open the dev server from another device, run Next.js so it listens on the LAN and add that device's origin to `allowedDevOrigins` in `frontend/solar-app/next.config.ts`.

`debugs/backfill_loop.py` and `debugs/backfill_evn.py` run one sync pass by hand. The server already does this on startup, so they are only for a one-off check.

## What the API does in the background

While `server.py` is running:

- Polls the live provider on `poll_interval_seconds` (default 5).
- Syncs SEMS daily generation and usage, fills yesterday's and today's sample gaps, rebuilds curtailment, and prunes old minute samples. The first pass waits for login, then repeats every 12 hours. It re-reads only as far back as the oldest hole, and at least the last 2 months.
- Syncs the EVN customer portal when `evn.portal.enabled` is set, then every 12 hours.
- Trains the yield forecast after the first history sync, then every 12 hours. Training needs a site location from the live poll and at least 20 days of history.
- Checks notice rules every 15 minutes, after history has synced.

`POST /api/sync` starts the same history pass in the background. It returns 409 if one is already running and 429 if the last one finished less than 2 minutes ago.

## Cloud, local, EVN, and the assistant

`cloud` logs in to GoodWe SEMS+ and reads station flow, daily curves, and inverter energy counters. Put the account in `config.json` under `cloud.account` and `cloud.password`. `region` can be `auto`, `hk`, `eu`, `au`, `us`, or `cn`.

`local` reads a GoodWe inverter on the LAN through Modbus. Set `local.host` to the inverter address.

Leave `station_id` empty to use the first station on the account.

`evn` is optional. Omit it and the built-in residential tiers (plus 8% VAT) are used. `evn.cycle_start_day` is the day the billing cycle resets. `evn.portal` pulls real meter readings and bills when `enabled` is true and `customer_id`, `username`, and `password` are set. `base_url` defaults to the EVN HCMC customer portal.

`ai` is optional. Without it, Assistant shows notices and reports that chat is off.

```json
{
  "ai": {
    "provider": "gemini",
    "model": "gemini-flash-lite-latest",
    "api_key": "..."
  }
}
```

`provider` can be `gemini` (needs `api_key`) or `ollama` (local, default `http://127.0.0.1:11434`). Gemini can call tools for a day, daily history, the billing cycle, curtailment, the weather forecast, and the hourly profile. The only setting it can propose is the battery reserve, and that change is applied only after you confirm it.

## Tests

```bash
source .venv/bin/activate
python -m unittest discover -s tests
```
