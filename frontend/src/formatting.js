export function formatDateTime(value) {
  return new Intl.DateTimeFormat(undefined, {
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
    month: "short",
    day: "numeric",
  }).format(new Date(value));
}

export function minutes(start, end) {
  return Math.round((new Date(end) - new Date(start)) / 60000);
}

export function groupByDay(sessions) {
  return sessions.reduce((days, session) => {
    const day = new Intl.DateTimeFormat(undefined, { weekday: "long" }).format(new Date(session.start));
    days[day] = days[day] || [];
    days[day].push(session);
    return days;
  }, {});
}
