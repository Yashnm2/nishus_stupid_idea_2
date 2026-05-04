import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Bot,
  CalendarCheck,
  Download,
  FileUp,
  MessageSquareText,
  RefreshCcw,
  Send,
} from "lucide-react";
import "./styles.css";

const API = import.meta.env.VITE_API_BASE_URL || "http://localhost:8001/api";

async function parseApiError(response) {
  try {
    const data = await response.json();
    return data.detail || data.message || response.statusText;
  } catch {
    return response.statusText || "Request failed";
  }
}

function formatDateTime(value) {
  return new Intl.DateTimeFormat(undefined, {
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
    month: "short",
    day: "numeric",
  }).format(new Date(value));
}

function minutes(start, end) {
  return Math.round((new Date(end) - new Date(start)) / 60000);
}

function groupByDay(sessions) {
  return sessions.reduce((days, session) => {
    const day = new Intl.DateTimeFormat(undefined, { weekday: "long" }).format(new Date(session.start));
    days[day] = days[day] || [];
    days[day].push(session);
    return days;
  }, {});
}

function StatusPill({ children, tone = "neutral" }) {
  return <span className={`pill pill-${tone}`}>{children}</span>;
}

function App() {
  const [plan, setPlan] = useState(null);
  const [calendarStatus, setCalendarStatus] = useState([]);
  const [message, setMessage] = useState("");
  const [log, setLog] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const days = useMemo(() => groupByDay(plan?.study_sessions || []), [plan]);

  async function load() {
    const [planRes, statusRes] = await Promise.all([fetch(`${API}/plan`), fetch(`${API}/calendar/status`)]);
    if (!planRes.ok) throw new Error(await parseApiError(planRes));
    if (!statusRes.ok) throw new Error(await parseApiError(statusRes));
    setPlan(await planRes.json());
    setCalendarStatus(await statusRes.json());
  }

  useEffect(() => {
    load().catch((err) => setError(err.message));
  }, []);

  async function upload(file) {
    if (!file) return;
    setBusy(true);
    setError("");
    const body = new FormData();
    body.append("file", file);
    try {
      const response = await fetch(`${API}/upload`, { method: "POST", body });
      if (!response.ok) throw new Error(await parseApiError(response));
      setPlan(await response.json());
      setLog([{ role: "system", text: `Imported ${file.name} and generated a study plan.` }]);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function sendMessage(event) {
    event.preventDefault();
    if (!message.trim()) return;
    const userText = message.trim();
    setMessage("");
    setBusy(true);
    setError("");
    setLog((items) => [...items, { role: "user", text: userText }]);
    try {
      const response = await fetch(`${API}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userText }),
      });
      if (!response.ok) throw new Error(await parseApiError(response));
      const data = await response.json();
      setPlan(data.plan);
      setLog((items) => [
        ...items,
        { role: "assistant", text: [data.reply, ...(data.warnings || [])].join(" ") },
      ]);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function connect(provider) {
    setError("");
    try {
      const response = await fetch(`${API}/calendar/${provider}/auth-url`);
      if (!response.ok) throw new Error(await parseApiError(response));
      const { url } = await response.json();
      window.location.href = url;
    } catch (err) {
      setError(err.message);
    }
  }

  async function sync(provider) {
    setBusy(true);
    setError("");
    try {
      const response = await fetch(`${API}/calendar/${provider}/sync`, { method: "POST" });
      if (!response.ok) throw new Error(await parseApiError(response));
      const data = await response.json();
      setPlan(data.plan);
      setLog((items) => [...items, { role: "system", text: data.message }]);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main>
      <header className="topbar">
        <div>
          <h1>Adaptive Study Planner</h1>
          <p>Import a timetable, generate study blocks, and keep the calendar current as plans change.</p>
        </div>
        <div className="top-actions">
          <button onClick={load} disabled={busy} title="Refresh">
            <RefreshCcw size={18} /> Refresh
          </button>
          <a className="button primary" href={`${API}/export/ics`}>
            <Download size={18} /> ICS
          </a>
        </div>
      </header>

      {error && <div className="error">{error}</div>}

      <section className="layout">
        <aside className="panel upload-panel">
          <div className="panel-title">
            <FileUp size={20} />
            <h2>Timetable</h2>
          </div>
          <label className="dropzone">
            <input
              type="file"
              accept=".csv,.xlsx,.ods,.pdf"
              onChange={(event) => upload(event.target.files?.[0])}
              disabled={busy}
            />
            <span>Upload CSV, XLSX, ODS, or PDF</span>
          </label>
          <div className="stats">
            <div>
              <strong>{plan?.classes?.length || 0}</strong>
              <span>Classes</span>
            </div>
            <div>
              <strong>{plan?.study_sessions?.length || 0}</strong>
              <span>Study sessions</span>
            </div>
          </div>
          <div className="calendar-list">
            <div className="panel-title compact">
              <CalendarCheck size={18} />
              <h2>Sync</h2>
            </div>
            {calendarStatus.map((item) => (
              <div className="calendar-row" key={item.provider}>
                <div>
                  <strong>{item.provider === "google" ? "Google" : "Outlook"}</strong>
                  <p>{item.message}</p>
                </div>
                {item.connected ? (
                  <button onClick={() => sync(item.provider)} disabled={busy}>Sync</button>
                ) : (
                  <button onClick={() => connect(item.provider)} disabled={!item.configured || busy}>
                    Connect
                  </button>
                )}
              </div>
            ))}
          </div>
        </aside>

        <section className="schedule">
          <div className="section-title">
            <h2>Week Plan</h2>
            <StatusPill tone={plan?.study_sessions?.length ? "good" : "neutral"}>
              {plan?.last_updated ? `Updated ${formatDateTime(plan.last_updated)}` : "No plan yet"}
            </StatusPill>
          </div>
          {Object.keys(days).length === 0 ? (
            <div className="empty">Upload a timetable with rows like “Monday 09:00-11:00 Engineering Mathematics”.</div>
          ) : (
            <div className="day-grid">
              {Object.entries(days).map(([day, sessions]) => (
                <div className="day-column" key={day}>
                  <h3>{day}</h3>
                  {sessions
                    .sort((a, b) => new Date(a.start) - new Date(b.start))
                    .map((session) => (
                      <article className="session" key={session.id}>
                        <div>
                          <strong>{session.module}</strong>
                          <span>{formatDateTime(session.start)} - {formatDateTime(session.end)}</span>
                        </div>
                        <StatusPill tone={session.status === "planned" ? "neutral" : "good"}>
                          {minutes(session.start, session.end)} min
                        </StatusPill>
                      </article>
                    ))}
                </div>
              ))}
            </div>
          )}
        </section>

        <aside className="panel chat-panel">
          <div className="panel-title">
            <Bot size={20} />
            <h2>Plan Chat</h2>
          </div>
          <div className="chat-log">
            {log.length === 0 ? (
              <div className="chat-empty">
                <MessageSquareText size={22} />
                <span>Try “Move math to Friday” or “I am behind on physics”.</span>
              </div>
            ) : (
              log.map((item, index) => (
                <div className={`bubble ${item.role}`} key={`${item.role}-${index}`}>
                  {item.text}
                </div>
              ))
            )}
          </div>
          <form className="chat-form" onSubmit={sendMessage}>
            <input
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              placeholder="Describe a change..."
              disabled={busy}
            />
            <button className="icon-button" disabled={busy || !message.trim()} title="Send">
              <Send size={18} />
            </button>
          </form>
        </aside>
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);
