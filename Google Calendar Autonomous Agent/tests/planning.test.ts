import { describe, expect, it } from "vitest";
import { agendaBriefing, scheduleHealth } from "../src/planning.js";

const event = (id: string, start: string, end: string, eventType = "default") => ({ id, summary: id, start: { dateTime: start }, end: { dateTime: end }, eventType });
describe("scheduleHealth", () => {
  it("identifies overlaps, back-to-back meetings, and missing focus time", () => {
    const events = [event("one", "2026-09-29T09:00:00Z", "2026-09-29T10:00:00Z"), event("two", "2026-09-29T09:30:00Z", "2026-09-29T10:30:00Z"), event("three", "2026-09-29T10:35:00Z", "2026-09-29T11:35:00Z")];
    const health = scheduleHealth(events, new Date("2026-09-29T09:00:00Z"), new Date("2026-09-29T12:00:00Z"));
    expect(health.conflicts).toHaveLength(1);
    expect(health.backToBackPairs).toBe(1);
    expect(health.suggestions).toContain("Resolve 1 overlapping commitment.");
    expect(health.suggestions).toContain("Protect a focus-time block for deep work.");
  });

  it("produces a compact agenda briefing", () => {
    const events = [event("focus", "2026-09-29T09:00:00Z", "2026-09-29T10:00:00Z", "focusTime")];
    const briefing = agendaBriefing(events, scheduleHealth(events, new Date("2026-09-29T08:00:00Z"), new Date("2026-09-29T12:00:00Z")));
    expect(briefing.headline).toBe("1 event on your schedule");
    expect(briefing.health.focusMinutes).toBe(60);
  });
});
