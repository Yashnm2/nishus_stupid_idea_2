export const API = import.meta.env.VITE_API_BASE_URL || "http://localhost:8001/api";

async function parseApiError(response) {
  try {
    const data = await response.json();
    return data.detail || data.message || response.statusText;
  } catch {
    return response.statusText || "Request failed";
  }
}

async function requestJson(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    throw new Error(await parseApiError(response));
  }
  return response.json();
}

export async function loadDashboard() {
  const [plan, calendarStatus] = await Promise.all([
    requestJson(`${API}/plan`),
    requestJson(`${API}/calendar/status`),
  ]);
  return { plan, calendarStatus };
}

export function uploadTimetable(file) {
  const body = new FormData();
  body.append("file", file);
  return requestJson(`${API}/upload`, { method: "POST", body });
}

export function sendChatMessage(message) {
  return requestJson(`${API}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
}

export async function getCalendarAuthUrl(provider) {
  const data = await requestJson(`${API}/calendar/${provider}/auth-url`);
  return data.url;
}

export function syncCalendar(provider) {
  return requestJson(`${API}/calendar/${provider}/sync`, { method: "POST" });
}
