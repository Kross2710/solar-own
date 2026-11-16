# Solar update — 8 November 2026

## Delivered

- Vietnam site clock for optimization, battery estimates, overview and sunrise/sunset displays, independent of the viewer's timezone.
- Dated residential tariffs (six tiers before November, five from 1 November), historical-period billing/savings/report calculations, explicit VAT and transition-cycle estimate metadata. Custom tariff tables remain custom.
- Optimization uses projected cycle purchases; hypothetical displaced grid energy is valued by the difference between tiered bills. Curtailment is presented in kWh, with any monetary equivalent explicitly distinguished from achievable savings.
- Replaced the fixed 21–23h warning with a conditional low-battery evening suggestion. Recommendations to use spare solar require the battery to be near full. Removed an unsupported fixed pre-cooling savings percentage.
- `/optimization/accuracy`: model selection, actual/predicted/baseline series, MAE/RMSE/MAPE/bias/R² and historical evaluation context. The selected backtest is cached during training. Direct cold starts initialize in the background, and refresh publishes a complete backtest snapshot.
- Payback scenarios compare completed months repriced at today's tariff with current-cycle pace. They are labeled scenarios, not a confidence interval; incomplete commissioning months are excluded from the completed-month scenario.

## Research gate

See [forecast diagnostic](forecast-diagnostic-2026-11-08.md). SEMS old curves are accessible, but 37 tested days yielded only two complete uncapped days. Synthetic-capping MAE was 3.37 kWh over six cases from those two days, insufficient to validate a potential-output training target. No production potential/usable model, full-history training backfill, notification integration, battery-upgrade simulator or hourly forecast was enabled.

## Verification and deployment

57 Python tests and three timezone/helper checks pass; TypeScript, ESLint and production builds pass. The Linux build is produced against the existing backend URL, independently of the running frontend. The working source is preserved locally for review; no Git commit or remote push was made.

Live services continue on ports 8787/8788 with the existing Cloudflare tunnel. A private pre-change source/build/database backup is retained at `/home/kross/solar-backups/update-20261108`. Klara remains a separate service/project/database and is not part of this update. The upgrade requires no phone/inverter settings changes.

Known limits: archived weather backtests are not measured issue-time forecast accuracy; tariff-transition volume allocation is approximate without change-date EVN meter readings; future payback scenarios hold current tariff/VAT fixed. Existing test-fixture background-task warnings and the existing Next.js multiple-lockfile warning remain.

Final live verification: dated tariff reports five tiers effective 2026-11-01. Accuracy serves 190 evaluated days from 220 historical days, selected model `hist_gbm`, MAE 4.99 versus baseline 5.48 kWh/day (skill 8.95%). Selected-model response was 8 ms internally after training; cold initialization returned a pending response in 12 ms. Baseline model selection matched the same dates and metrics. Mobile UI verified Money, payback scenarios, Vietnam hour marker, curtailed-energy presentation, the accuracy chart and switching to the baseline. Production potential equals actual plus attributed loss, within rounding tolerance.
