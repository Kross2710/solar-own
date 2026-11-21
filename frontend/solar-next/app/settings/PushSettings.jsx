"use client";

import {useEffect, useState} from "react";
import {usePreferences} from "../i18n/context";

const DEVICE_KEY = "solar-push-device";
const API = "/api/push";

async function request(path, {method = "GET", token, body, signal} = {}) {
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body) headers["Content-Type"] = "application/json";
  const response = await fetch(API + path, {
    method, headers, body: body && JSON.stringify(body), signal, cache: "no-store",
  });
  if (!response.ok) throw new PushRequestError(response.status);
  return response.status === 204 ? null : response.json();
}

class PushRequestError extends Error {
  constructor(status) {
    super(`Push API status ${status}`);
    this.status = status;
  }
}

function applicationKey(value) {
  const encoded = value.replaceAll("-", "+").replaceAll("_", "/");
  return Uint8Array.from(atob(encoded.padEnd(Math.ceil(encoded.length / 4) * 4, "=")), char => char.charCodeAt(0));
}

export default function PushSettings() {
  const {t, lang} = usePreferences();
  const [setup, setSetup] = useState({status: "Loading notification settings…"});
  const [active, setActive] = useState(false);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    const {signal} = controller;
    async function load() {
      const ios = /iPad|iPhone|iPod/.test(navigator.userAgent)
        || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
      if (!window.isSecureContext) {
        return {status: "Open Home Solar over HTTPS to enable notifications."};
      }
      if (ios && !(navigator.standalone || matchMedia("(display-mode: standalone)").matches)) {
        return {status: "In Safari, tap Share → Add to Home Screen, then open Home Solar from its icon."};
      }
      if (!("serviceWorker" in navigator && "PushManager" in window && "Notification" in window)) {
        return {status: "Web Push is unavailable in this browser. On iPhone, use iOS 16.4 or later."};
      }

      const config = await request("/config", {signal});
      if (!config.enabled) return {status: "Web Push has not been configured on this server."};

      await navigator.serviceWorker.register("/sw.js");
      const worker = await navigator.serviceWorker.ready;
      const key = applicationKey(config.publicKey);
      let subscription = await worker.pushManager.getSubscription();
      const token = localStorage.getItem(DEVICE_KEY);
      if (subscription) {
        const currentKey = new Uint8Array(subscription.options.applicationServerKey ?? []);
        if (currentKey.length !== key.length || !key.every((byte, index) => byte === currentKey[index])) {
          await subscription.unsubscribe();
          subscription = null;
        }
      }
      if (token) {
        const device = await request("/device", {token, signal});
        if (device.endpoint && device.endpoint === subscription?.endpoint) {
          if (device.language !== lang) await request("/device", {method: "PATCH", token, signal, body: {language: lang}});
          return {worker, key, active: true};
        }
        if (device.endpoint) await request("/device", {method: "DELETE", token, signal});
      }
      return {worker, key};
    }

    load().then(result => {
      if (!signal.aborted) {
        setSetup(result);
        setActive(Boolean(result.active));
      }
    }).catch(() => {
      if (!signal.aborted) setSetup({status: "Could not load notification settings. Reload to try again."});
    });
    return () => controller.abort();
  }, [lang]);

  async function enable(event) {
    event.preventDefault();
    setBusy(true);
    setNotice("");
    try {
      const token = localStorage.getItem(DEVICE_KEY) || crypto.randomUUID();
      // Start the permission request while the submit gesture is still active on iOS.
      const subscription = await setup.worker.pushManager.subscribe({userVisibleOnly: true, applicationServerKey: setup.key});
      localStorage.setItem(DEVICE_KEY, token);
      await request("/device", {
        method: "PUT", token, body: {code: code.trim(), subscription: subscription.toJSON(), language: lang},
      });
      setActive(true);
      setCode("");
      setNotice("Alerts are enabled on this device.");
    } catch (error) {
      if (Notification.permission === "denied") {
        setNotice("Allow notifications for Home Solar in your device settings, then try again.");
      } else if (error.status === 403) {
        setNotice("The device setup code is incorrect.");
      } else {
        setNotice("Could not enable notifications. Please try again.");
      }
    } finally {
      setBusy(false);
    }
  }

  async function disable() {
    setBusy(true);
    setNotice("");
    try {
      const token = localStorage.getItem(DEVICE_KEY);
      await request("/device", {method: "DELETE", token});
      const subscription = await setup.worker.pushManager.getSubscription();
      await subscription?.unsubscribe();
      localStorage.removeItem(DEVICE_KEY);
      setActive(false);
      setNotice("Alerts are disabled on this device.");
    } catch {
      setNotice("Could not finish disabling notifications. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  async function sendTest() {
    setBusy(true);
    setNotice("");
    try {
      const token = localStorage.getItem(DEVICE_KEY);
      await request("/test", {method: "POST", token});
      setNotice("Test accepted by the push service. Check your notifications.");
    } catch (error) {
      if (error.status === 429) {
        setNotice("Wait up to one minute before sending another test.");
      } else if (error.status === 410 || error.status === 404) {
        setActive(false);
        const subscription = await setup.worker.pushManager.getSubscription().catch(() => null);
        await subscription?.unsubscribe().catch(() => {});
        setNotice("This subscription expired. Enable notifications again.");
      } else {
        setNotice("Could not send the test notification. Please try again.");
      }
    } finally {
      setBusy(false);
    }
  }

  return <section className="panel push-settings" aria-labelledby="push-title">
    <h2 id="push-title">{t("Notifications")}</h2>
    <p>{t("Get an alert when the battery reaches 20% while discharging or the primary inverter feed stops for 10 minutes. You’ll also be notified when it recovers.")}</p>
    {setup.status ? <p role="status">{t(setup.status)}</p> : active ? (
      <div className="push-actions">
        <button type="button" disabled={busy} onClick={sendTest}>{t("Send test")}</button>
        <button type="button" disabled={busy} onClick={disable}>{t("Disable on this device")}</button>
      </div>
    ) : (
      <form className="push-actions" onSubmit={enable}>
        <label htmlFor="push-code">{t("Device setup code")}
          <input id="push-code" type="password" required autoComplete="off" maxLength={256}
            value={code} onChange={event => setCode(event.target.value)} />
        </label>
        <button type="submit" disabled={busy || !code.trim()}>{t("Enable notifications")}</button>
      </form>
    )}
    {notice && <p role="status">{t(notice)}</p>}
  </section>;
}
