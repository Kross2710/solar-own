# Home Solar

A home energy dashboard for a hybrid solar system. It shows live power flow, daily generation, and how much of the house load came from solar versus the grid.

The UI is a Next.js app. A FastAPI service polls the inverter source, stores history in SQLite, and serves `/api/*`. In development, Next.js proxies those routes to the API, so a phone on the same LAN can open the site without calling `localhost` on itself.

## Stack

- Next.js, React, and SWR for the dashboard
- FastAPI and uvicorn for the API
- SQLite for minute samples and daily totals
- GoodWe SEMS+ for cloud live data and history
- Optional local Modbus reads through the `goodwe` package
- EVN residential tariff math for savings

`source` in the config selects the provider: `mock`, `cloud`, or `local`.

## Screens

| Route | What it shows |
|---|---|
| `/` | Live PV, home load, battery, and grid, plus today's energy split |
| `/history` | Daily generation, month and year totals, self-powered days |
| `/money` | WIP |
| `/optimization` | WIP |

## Run it

Use Python 3.12+ and Node 20+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install fastapi uvicorn httpx goodwe

cd frontend/solar-app
npm install
```

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
  "host": "127.0.0.1",
  "port": 8787
}
```

`config.json` is gitignored. Do not commit inverter passwords, portal logins, or API keys.

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

Open [http://localhost:3000](http://localhost:3000). The API listens on [http://127.0.0.1:8787](http://127.0.0.1:8787). Next.js rewrites `/api/*` to that process. Override the target with `BACKEND_URL` if it is not on port 8787.

To open the dev server from another device, run Next.js so it listens on the LAN and add that device's origin to `allowedDevOrigins` in `frontend/solar-app/next.config.ts`.

## Cloud and local sources

`cloud` logs in to GoodWe SEMS+ and reads station flow, daily curves, and inverter energy counters. Put the account in `config.json` under `cloud.account` and `cloud.password`. `region` can be `auto`, `hk`, `eu`, `au`, `us`, or `cn`.

`local` reads a GoodWe inverter on the LAN through Modbus. Set `local.host` to the inverter address.

Leave `station_id` empty to use the first station on the account.

## Tests

```bash
source .venv/bin/activate
python -m unittest discover -s tests
```
