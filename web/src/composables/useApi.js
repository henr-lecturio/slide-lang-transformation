export async function apiGet(url) {
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) {
    const body = await safeJson(res);
    throw new Error(body.error || `GET ${url} failed (${res.status})`);
  }
  return await res.json();
}

export async function apiPost(url, payload = {}) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const body = await safeJson(res);
  if (!res.ok) {
    throw new Error(body.error || `POST ${url} failed (${res.status})`);
  }
  return body;
}

async function safeJson(res) {
  try {
    return await res.json();
  } catch {
    return {};
  }
}
