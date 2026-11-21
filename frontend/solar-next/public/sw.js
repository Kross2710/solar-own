/* Home Solar uses live data. This worker handles notifications only. */
self.addEventListener("push", event => {
  let message = {};
  try {
    message = event.data?.json() || {};
  } catch {
    // WebKit expects a visible notification for every push.
  }
  event.waitUntil(self.registration.showNotification(message.title || "Home Solar", {
    body: message.body || "",
    tag: message.tag,
    icon: "/icons/home-solar-192.png",
    data: { path: message.path === "/settings" ? "/settings" : "/" },
  }));
});

self.addEventListener("notificationclick", event => {
  const path = event.notification.data?.path === "/settings" ? "/settings" : "/";
  const target = new URL(path, self.location.origin).href;
  event.notification.close();
  event.waitUntil((async () => {
    const windows = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
    const existing = windows.find(client => client.url === target);
    return existing ? existing.focus() : self.clients.openWindow(target);
  })());
});
