import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import ts from 'typescript';
import { createRequire } from 'node:module';
const nodeRequire = createRequire(import.meta.url);
const cache = new Map();
const root = path.resolve(import.meta.dirname, '..');
// Compile pure TS helpers using the project's own TypeScript, without another test runtime.
function load(file) {
  if (cache.has(file)) return cache.get(file).exports;
  const compiled = { exports: {} }; cache.set(file, compiled);
  const js = ts.transpileModule(fs.readFileSync(file, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const localRequire = name => name.startsWith('@/') ? load(path.join(root, name.slice(2) + '.ts')) : name.startsWith('.') ? load(path.resolve(path.dirname(file), name + '.ts')) : nodeRequire(name);
  new Function('require', 'module', 'exports', js)(localRequire, compiled, compiled.exports);
  return compiled.exports;
}
const { siteClock } = load(path.join(root, 'lib/time.ts'));
const { minutesLeftInWindow, batteryOutlook, buildSuggestions } = load(path.join(root, 'app/optimization/optimization.helpers.ts'));

test('Vietnam day/hour and countdown ignore process timezone', () => {
  const instant = new Date('2026-11-06T16:52:00Z');
  assert.deepEqual(siteClock(instant), { day: '2026-11-06', hour: 23, minute: 52 });
  assert.equal(minutesLeftInWindow({ from: 7, to: 13 }, instant), null);
  assert.equal(minutesLeftInWindow({ from: 7, to: 13 }, new Date('2026-11-06T01:52:00Z')), 248);
  assert.deepEqual(siteClock(new Date('2026-11-06T17:02:00Z')), { day: '2026-11-07', hour: 0, minute: 2 });
});
test('battery clock uses Vietnam time across day boundary', () => {
  const result = batteryOutlook({ battery_soc: 50, battery_capacity_kwh: 20, battery_power_w: -1000, battery_reserve_percent: 20 }, new Date('2026-11-06T16:52:00Z'));
  assert.match(result.detail, /05:50/);
});
test('late night has no fixed 21-23h warning and spare sun needs battery room checked', () => {
  const metrics = { pv_power_w: 5000, load_power_w: 1000, battery_soc: 40, battery_capacity_kwh: 20 };
  assert.equal(buildSuggestions({ metrics, kind: 'sunny', hour: 12 }).some(s => s.id === 'wash-now'), false);
  assert.equal(buildSuggestions({ metrics: { ...metrics, battery_soc: 100 }, kind: 'sunny', hour: 12 }).some(s => s.id === 'wash-now'), true);
});
