import { calendar_v3 } from "googleapis";

type Event = calendar_v3.Schema$Event;
const asDate = (event: Event, key: "start" | "end") => new Date(event[key]?.dateTime ?? event[key]?.date ?? "");

export type ScheduleHealth = {
  eventCount: number;
  meetingMinutes: number;
  focusMinutes: number;
  longestFreeBlockMinutes: number;
  backToBackPairs: number;
  conflicts: Array<{ firstId?: string | null; secondId?: string | null }>;
  suggestions: string[];
};

export function scheduleHealth(events: Event[], rangeStart: Date, rangeEnd: Date): ScheduleHealth {
  const sorted = events
    .filter(event => !event.transparency || event.transparency !== "transparent")
    .map(event => ({ event, start: asDate(event, "start"), end: asDate(event, "end") }))
    .filter(item => !Number.isNaN(+item.start) && !Number.isNaN(+item.end))
    .sort((a, b) => +a.start - +b.start);
  let meetingMinutes = 0, focusMinutes = 0, backToBackPairs = 0, cursor = rangeStart, longestFreeBlockMinutes = 0;
  const conflicts: ScheduleHealth["conflicts"] = [];
  for (let index = 0; index < sorted.length; index++) {
    const item = sorted[index];
    const minutes = Math.max(0, (+item.end - +item.start) / 60000);
    if (item.event.eventType === "focusTime") focusMinutes += minutes; else meetingMinutes += minutes;
    if (item.start > cursor) longestFreeBlockMinutes = Math.max(longestFreeBlockMinutes, (+item.start - +cursor) / 60000);
    const previous = sorted[index - 1];
    if (previous) {
      const gap = (+item.start - +previous.end) / 60000;
      if (gap >= 0 && gap <= 5) backToBackPairs++;
      if (gap < 0) conflicts.push({ firstId: previous.event.id, secondId: item.event.id });
    }
    if (item.end > cursor) cursor = item.end;
  }
  longestFreeBlockMinutes = Math.max(longestFreeBlockMinutes, (+rangeEnd - +cursor) / 60000);
  const suggestions: string[] = [];
  if (conflicts.length) suggestions.push(`Resolve ${conflicts.length} overlapping commitment${conflicts.length === 1 ? "" : "s"}.`);
  if (backToBackPairs >= 2) suggestions.push("Add 10–15 minute buffers between consecutive meetings.");
  if (!focusMinutes && meetingMinutes >= 120) suggestions.push("Protect a focus-time block for deep work.");
  if (longestFreeBlockMinutes < 60) suggestions.push("No uninterrupted hour remains; move lower-priority work or shorten a meeting.");
  return { eventCount: sorted.length, meetingMinutes, focusMinutes, longestFreeBlockMinutes, backToBackPairs, conflicts, suggestions };
}

export function agendaBriefing(events: Event[], health: ScheduleHealth) {
  return {
    headline: events.length ? `${events.length} event${events.length === 1 ? "" : "s"} on your schedule` : "Your calendar is clear",
    nextEvent: events.find(event => new Date(event.start?.dateTime ?? event.start?.date ?? 0) > new Date()) ?? null,
    health,
    events: events.map(event => ({ id: event.id, summary: event.summary, start: event.start, end: event.end, location: event.location, meetLink: event.hangoutLink, eventType: event.eventType }))
  };
}
