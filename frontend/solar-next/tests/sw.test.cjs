const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const {test} = require("node:test");
const vm = require("node:vm");

const origin = "https://solar.example";
const source = fs.readFileSync(path.join(__dirname, "../public/sw.js"), "utf8");

async function click(createWindows) {
  const calls = [];
  const self = {
    location: {origin},
    clients: {
      matchAll: async () => createWindows(calls),
      openWindow: async url => { calls.push(["open", url]); },
    },
    addEventListener(type, handler) {
      if (type === "notificationclick") this.click = handler;
    },
  };
  vm.runInNewContext(source, {self, URL});

  let task;
  self.click({
    notification: {data: {path: "/settings"}, close() {}},
    waitUntil(promise) { task = promise; },
  });
  await task;
  return calls;
}

function appWindow(calls, route) {
  return {
    url: origin + route,
    frameType: "top-level",
    async focus() { calls.push(["focus", route]); },
    async navigate(url) {
      calls.push(["navigate", url]);
      return this;
    },
  };
}

test("focuses an existing window on the target route", async () => {
  const calls = await click(calls => [appWindow(calls, "/overview"), appWindow(calls, "/settings")]);
  assert.deepEqual(calls, [["focus", "/settings"]]);
});

test("focuses and navigates an existing Home Solar window on another route", async () => {
  const calls = await click(calls => [appWindow(calls, "/overview")]);
  assert.deepEqual(calls, [["focus", "/overview"], ["navigate", origin + "/settings"]]);
});

test("opens the target when there is no eligible window", async () => {
  const calls = await click(calls => [
    {...appWindow(calls, "/settings"), frameType: "nested"},
    {...appWindow(calls, "/settings"), url: "https://other.example/settings"},
  ]);
  assert.deepEqual(calls, [["open", origin + "/settings"]]);
});

test("falls back to opening the target if navigation fails", async () => {
  const calls = await click(calls => [{
    ...appWindow(calls, "/overview"),
    async navigate() { throw new Error("window closed"); },
  }]);
  assert.deepEqual(calls, [["focus", "/overview"], ["open", origin + "/settings"]]);
});
