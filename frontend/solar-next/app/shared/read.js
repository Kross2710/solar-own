export async function read(endpoint) {
  try {
    const url = new URL("/api/" + endpoint, process.env.BACKEND_URL || "http://127.0.0.1:8787");
    const response = await fetch(url, {cache:"no-store", signal:AbortSignal.timeout(10000)});
    return response.ok ? await response.json() : null;
  } catch {
    return null;
  }
}
