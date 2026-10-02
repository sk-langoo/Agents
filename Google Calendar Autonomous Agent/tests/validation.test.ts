import { describe, expect, it } from "vitest";
import { availabilityQuerySchema, eventPatchSchema, eventSchema } from "../src/validation.js";

describe("event validation", () => {
  const validEvent = { summary: "Planning", start: "2026-09-29T09:00:00-04:00", end: "2026-09-29T10:00:00-04:00" };

  it("accepts a complete offset-aware event", () => {
    expect(eventSchema.parse({ ...validEvent, recurrence: ["RRULE:FREQ=WEEKLY;BYDAY=MO"] })).toMatchObject(validEvent);
  });

  it("rejects a local time without an offset", () => {
    expect(() => eventSchema.parse({ ...validEvent, start: "2026-09-29T09:00:00" })).toThrow();
  });

  it("rejects an event whose end is not after its start", () => {
    expect(() => eventSchema.parse({ ...validEvent, end: validEvent.start })).toThrow(/end must be after start/);
  });

  it("rejects non-RRULE recurrence text and malformed guest addresses", () => {
    expect(() => eventSchema.parse({ ...validEvent, recurrence: ["weekly"], attendees: [{ email: "not-email" }] })).toThrow();
  });

  it("allows a partial update but validates start/end when both are supplied", () => {
    expect(eventPatchSchema.parse({ location: "Room 4" })).toEqual({ location: "Room 4" });
    expect(() => eventPatchSchema.parse({ start: "2026-09-29T12:00:00Z", end: "2026-09-29T11:00:00Z" })).toThrow(/end must be after start/);
  });

  it("does not permit changing a Google Calendar event type after creation", () => {
    expect(() => eventPatchSchema.parse({ eventType: "focusTime" })).toThrow();
  });
});

describe("availability query validation", () => {
  it("coerces a valid duration and rejects reversed ranges", () => {
    expect(availabilityQuerySchema.parse({ start: "2026-09-29T09:00:00Z", end: "2026-09-29T11:00:00Z", minutes: "30" }).minutes).toBe(30);
    expect(() => availabilityQuerySchema.parse({ start: "2026-09-29T11:00:00Z", end: "2026-09-29T09:00:00Z", minutes: 30 })).toThrow(/end must be after start/);
  });
});
