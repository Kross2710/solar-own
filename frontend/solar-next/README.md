# Home Solar frontend

The production frontend contains Overview, History, Money, Optimization, Assistant and Settings. Use Node.js 22 or newer and run commands from this directory.

The host runs this app through the `frontend/solar-app` symlink. On the host, set `BACKEND_URL=http://127.0.0.1:8788` for both the build and the service. Start with `npm run start -- -H 0.0.0.0 -p 8787`. The previous source is in `frontend/solar-app-legacy`.

## Run a local preview

1. Run `npm ci`.
2. Set `BACKEND_URL` in the local, gitignored `.env.local` to the existing Home Solar backend origin. The default is `http://127.0.0.1:8787`. Next.js reads this setting during the build for the backend API proxy, so rebuild if the origin changes.
3. Run `npm run build` followed by `npm run start:rc`.
4. Open http://127.0.0.1:3002. The development server is available separately with `npm run dev` on port 3001.

## Settings

The language selector switches between English and Vietnamese, including the requested Assistant reply language. Advanced readings reveal inverter specifications, daily consumption and battery discharge, the projected grid tariff, and forecast model diagnostics. Preferences are stored in first-party cookies on the review host for one year. New browsers start in English with advanced readings off.

## Data

Overview polls inverter metrics every five seconds while visible. Positive grid power means import; positive battery power means charging. The time axis uses Vietnam time. History requests up to 366 daily records. Money uses the current EVN billing cycle. Live Assistant messages and notice dismissals go to the configured backend.

Append `?demo=1` to review the sample system offline. Navigation retains demo mode. Demo chat replies and dismissals are local, and its chat history is stored separately from live conversations.
