const MS_PER_DAY = 86_400_000;

function atMidnight(d: Date): number {
  return Math.floor(new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime() / MS_PER_DAY);
}

export function daysUntil(endDate: string | null, today: Date = new Date()): number | null {
  if (!endDate) return null;
  const end = new Date(endDate + "T00:00:00");
  return atMidnight(end) - atMidnight(today);
}

export function ddayLabel(endDate: string | null, today: Date = new Date()): string | null {
  const d = daysUntil(endDate, today);
  // d < 0 means the show already ended — no countdown applies. "D-day" is
  // reserved for the final day only (d === 0), not for any past date.
  if (d === null || d < 0) return null;
  return d === 0 ? "D-day" : `D-${d}`;
}

export function isClosingSoon(endDate: string | null, today: Date = new Date()): boolean {
  const d = daysUntil(endDate, today);
  return d !== null && d >= 0 && d <= 7;
}
