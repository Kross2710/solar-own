# Forecast diagnostic — 8 November 2026 (Vietnam)

Production's forecast model is retained. The proposed potential/usable model has not passed its prerequisite data-quality gate.

## Observed evidence

- SEMS returned older intraday curves on 2 April, 26 May, 20 July and 13 September 2026. Old-curve retrieval is possible; the April commissioning-day curve is incomplete.
- Probed/cached 37 distinct completed days, including 12 recent days and the 24 lowest measured-generation days (with overlap).
- 36 had sufficient daytime coverage. Of these, 34 reached full SOC or otherwise failed the uncapped-day screen. Only 2 were complete uncapped days.
- On those 2 days, simulated capping at 10:00, 11:00 and 12:00 gave an aggregate potential-estimator MAE of **3.37 kWh**. Six simulated cases from two days are not six independent days, nor a reliable population error estimate.
- Screening rule set before evaluating: at least 20 distinct uncapped days and synthetic-capping MAE <=3 kWh. Result: **insufficient evidence**, with the observed MAE also above the screening threshold.

| Day | Synthetic cap begins | True kWh | Estimated potential kWh | Error kWh |
| --- | --- | --- | --- | --- |
| 2026-05-29 | 10:00 | 16.61 | 10.1 | -6.51 |
| 2026-05-29 | 11:00 | 16.61 | 17.7 | 1.09 |
| 2026-05-29 | 12:00 | 16.61 | 24.7 | 8.09 |
| 2026-09-23 | 10:00 | 25.21 | 23.0 | -2.21 |
| 2026-09-23 | 11:00 | 25.21 | 23.3 | -1.91 |
| 2026-09-23 | 12:00 | 25.21 | 24.8 | -0.41 |

The synthetic curve replaces hidden afternoon PV with capped load and artificial full SOC. Hidden afternoon peaks are not passed to the estimator. Uncapped-day selection uses complete historical truth to identify eligible evaluation days, not as a production feature. This test is only a reconstruction diagnostic; uncapped days may be unrepresentative of sunny early-fill days.

## Corrections delivered

`potential_kwh` now means actual + attributed curtailment. The half-sine envelope over the entire day is exposed separately as `envelope_kwh`; it must not be used as measured physical potential. No research-derived estimate was written over actual daily totals, and production model selection/weights were not changed.

## Next gate

Do not launch a full potential-target training/backfill or promote a model on these two days. Improve/validate the estimator using hourly radiation and uncapped intervals, or obtain a larger independently measured uncapped dataset first. A future experiment must forecast load and sunrise SOC using only information available at issue time and compare usable-output predictions on the exact same held-out dates as the existing model. Archived observed weather is not a substitute for issue-time weather forecasts.

Surplus alerts, battery-size simulations and hourly production forecasts remain subsequent work; no notifications were enrolled/sent, no BMS/inverter settings were changed, and no battery purchase recommendation is inferred from this result.

## Reproduce

Run `tools/research/forecast_diagnostic.py --config-root <private deployment> --cache <private cache> --recent-days 12 --low-yield-days 24 --pause 3` from a copy of the repository with access to the configured SEMS provider. Each successful day is cached independently. Cache files are ignored by Git; the tool stops on a provider error and can resume. It does not modify production daily, curtailment or weather tables (the existing history store opens/initializes its schema as usual).
