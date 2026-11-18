"""Read-only SEMS probes and censored-curve diagnostics; never trains production models.

Run from the repository root. Cache is resumable, one file per completed day.
No daily totals, weather, tariff, battery settings or production tables are modified.
"""
import argparse
import asyncio
from collections import Counter
from datetime import date, datetime
import json
import math
from pathlib import Path
import statistics
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend.config import load_config
from backend.provider_factory import build_provider
from providers.analytics import estimate_curtailment, _mins
from providers.base import VN_TZ
from providers.history import HistoryStore


def valid_curve(points):
    samples = {p.get('t'): p for p in points if p.get('pv') is not None and _mins(p.get('t')) is not None}
    ordered = sorted(samples.values(), key=lambda p: _mins(p['t']))
    day = [p for p in ordered if 6 * 60 <= _mins(p['t']) < 18 * 60]
    complete = len(day) >= 130 and all(_mins(b['t']) - _mins(a['t']) <= 10 for a, b in zip(day, day[1:]))
    known_soc = bool(day) and all(p.get('soc') is not None for p in day)
    uncapped = known_soc and max(p['soc'] for p in day) < 95
    return ordered, complete, uncapped


def artificial_curtailment(points, cutoff):
    """Simulate a full battery after cutoff; no hidden afternoon peak is reused.

    Only pre-cutoff PV determines the simulated absorbable load. The estimator
    receives the capped curve and artificial SOC, not the withheld real afternoon.
    """
    before = [p['pv'] for p in points if _mins(p['t']) < cutoff and p.get('pv') is not None]
    load = min(3000, max(before, default=0) * 0.35)
    return [{**p, 'pv': min(p['pv'], load) if _mins(p['t']) >= cutoff else p['pv'],
             'soc': 100 if _mins(p['t']) >= cutoff else 60, 'grid': 0} for p in points]


def evaluate(cache, capacity):
    results, rejected, records = [], Counter(), []
    for file in sorted(cache.glob('????-??-??.json')):
        curve = json.loads(file.read_text())
        points, complete, uncapped = valid_curve(curve.get('points', []))
        if not complete:
            rejected['incomplete_curve'] += 1
            continue
        estimate = estimate_curtailment(points, capacity_kw=capacity)
        day = file.stem
        records.append({'day': day, 'actual_kwh': estimate['actual_kwh'],
                        'estimated_potential_kwh': estimate['potential_kwh'],
                        'estimated_lost_kwh': estimate['lost_kwh'], 'uncapped': uncapped})
        if not uncapped:
            rejected['curtailed_or_unknown_soc'] += 1
            continue
        actual = sum(p['pv'] for p in points) * 5 / 60 / 1000
        for cutoff in (10 * 60, 11 * 60, 12 * 60):
            simulated = estimate_curtailment(artificial_curtailment(points, cutoff), capacity_kw=capacity)
            results.append({'day': day, 'cutoff': cutoff // 60, 'true_kwh': round(actual, 2),
                            'estimated_kwh': simulated['potential_kwh'],
                            'error_kwh': round(simulated['potential_kwh'] - actual, 2)})
    unique_days = len({r['day'] for r in results})
    mae = statistics.mean(abs(r['error_kwh']) for r in results) if results else None
    # A screening gate, not proof of physical potential or confidence coverage.
    passed = unique_days >= 20 and mae is not None and mae <= 3
    return {'cached_days': len(list(cache.glob('????-??-??.json'))), 'eligible_uncapped_days': unique_days,
            'excluded': dict(rejected), 'screening_mae_kwh': mae,
            'gate': 'pass' if passed else 'insufficient_evidence' if unique_days < 20 else 'fail',
            'gate_rule': 'at least 20 distinct complete uncapped days and synthetic-capping MAE <=3 kWh; further weather-stratified validation still required',
            'limitations': ['uncapped days may be a biased weather/load sample', 'historical actual weather is not forecast-time weather',
                           'potential is estimated, not measured', 'future load and sunrise SOC must be predicted without leakage'],
            'screening_results': results, 'daily_estimates': records}


async def main(args):
    cfg = load_config(args.config_root)
    store = HistoryStore(args.config_root / 'history.db')
    today = datetime.now(VN_TZ).date().isoformat()
    days = [r['day'] for r in store.daily(4000) if r.get('kwh') is not None and r['day'] < today]
    if not days:
        raise SystemExit('No completed historical days')
    old = list(dict.fromkeys(days[int((len(days)-1)*x)] for x in (0, .25, .5, .75)))
    lowest = [r['day'] for r in sorted(store.daily(4000), key=lambda r: r.get('kwh') if r.get('kwh') is not None else float('inf')) if r.get('kwh') is not None and r['day'] < today][:args.low_yield_days]
    chosen = list(dict.fromkeys(old + days[-args.recent_days:] + lowest))
    args.cache.mkdir(parents=True, exist_ok=True)
    provider = build_provider(cfg, source=cfg.get('history_source') or cfg.get('source'))
    probes = []
    try:
        for day in chosen:
            target = args.cache / (day + '.json')
            if target.exists():
                continue
            try:
                curve = await provider.fetch_day_curve(day)
                points = curve.get('points') or []
                if not points:
                    probes.append({'day': day, 'status': 'empty'})
                    continue
                temporary = target.with_suffix('.tmp')
                temporary.write_text(json.dumps(curve))
                temporary.replace(target)
                probes.append({'day': day, 'status': 'ok', 'points': len(points)})
            except Exception as error:
                probes.append({'day': day, 'status': 'error', 'error_type': type(error).__name__})
                break  # stop on a rate limit/auth/network failure; cached successes remain
            finally:
                await asyncio.sleep(args.pause)
    finally:
        await provider.close()
    report = evaluate(args.cache, cfg.get('capacity_kw'))
    report['probes'] = probes
    report['old_curve_dates'] = old
    report['old_curve_access'] = {day: (args.cache / (day + '.json')).exists() for day in old}
    (args.cache / 'report.json').write_text(json.dumps(report, indent=2))
    print(json.dumps({key: value for key, value in report.items() if key not in ('screening_results','daily_estimates')}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config-root', type=Path, default=Path.cwd())
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--recent-days', type=int, default=12)
    parser.add_argument('--low-yield-days', type=int, default=24)
    parser.add_argument('--pause', type=float, default=3)
    options = parser.parse_args()
    if options.recent_days < 1 or options.pause < 1:
        parser.error('recent-days must be positive; pause must be >=1 second')
    asyncio.run(main(options))
