import { describe, expect, it } from "vitest";
import { findFreeSlots } from "../src/calendar.js";

describe("findFreeSlots", () => {
  it("returns gaps that meet the requested duration", () => {
    const events = [{ start: { dateTime: "2026-09-29T10:00:00Z" }, end: { dateTime: "2026-09-29T11:00:00Z" } }];
    const result = findFreeSlots(events, new Date("2026-09-29T09:00:00Z"), new Date("2026-09-29T13:00:00Z"), 90);
    expect(result.slots).toEqual([{ start: "2026-09-29T11:00:00.000Z", end: "2026-09-29T13:00:00.000Z", minutes: 120 }]);
  });

  it("merges overlapping busy blocks before calculating openings", () => {
    const events = [
      { start: { dateTime: "2026-09-29T10:00:00Z" }, end: { dateTime: "2026-09-29T12:00:00Z" } },
      { start: { dateTime: "2026-09-29T11:00:00Z" }, end: { dateTime: "2026-09-29T13:00:00Z" } }
    ];
    const result = findFreeSlots(events, new Date("2026-09-29T09:00:00Z"), new Date("2026-09-29T14:00:00Z"), 60);
    expect(result.slots).toEqual([
      { start: "2026-09-29T09:00:00.000Z", end: "2026-09-29T10:00:00.000Z", minutes: 60 },
      { start: "2026-09-29T13:00:00.000Z", end: "2026-09-29T14:00:00.000Z", minutes: 60 }
    ]);
  });
});
