import { z } from "zod";

export const rfc3339 = z.string().datetime({ offset: true });

const eventFields = z.object({
  summary: z.string().min(1),
  start: rfc3339,
  end: rfc3339,
  description: z.string().optional(),
  location: z.string().optional(),
  colorId: z.string().optional(),
  conference: z.boolean().optional(),
  recurrence: z.array(z.string().startsWith("RRULE:")).optional(),
  eventType: z.enum(["default", "focusTime", "outOfOffice"]).optional(),
  tags: z.record(z.string().max(44), z.string().max(1024)).optional(),
  attendees: z.array(z.object({ email: z.string().email(), optional: z.boolean().optional() })).optional()
});

export const eventSchema = eventFields.superRefine((value, ctx) => {
  if (new Date(value.end) <= new Date(value.start)) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, path: ["end"], message: "end must be after start" });
  }
});

export const eventPatchSchema = eventFields.omit({ eventType: true }).partial().strict().superRefine((value, ctx) => {
  if (value.start && value.end && new Date(value.end) <= new Date(value.start)) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, path: ["end"], message: "end must be after start" });
  }
});

export const availabilityQuerySchema = z.object({
  start: rfc3339,
  end: rfc3339,
  minutes: z.coerce.number().int().positive(),
  calendars: z.string().optional()
}).superRefine((value, ctx) => {
  if (new Date(value.end) <= new Date(value.start)) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, path: ["end"], message: "end must be after start" });
  }
});
