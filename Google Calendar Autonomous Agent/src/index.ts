import express from "express";
import { z } from "zod";
import { config } from "./config.js";
import { CalendarService, findFreeSlots } from "./calendar.js";
import OpenAI from "openai";
import { availabilityQuerySchema, eventPatchSchema, eventSchema } from "./validation.js";
import { agendaBriefing, scheduleHealth } from "./planning.js";

const app = express();
const calendar = new CalendarService();
app.use(express.json());

app.get("/health", (_, res) => res.json({ ok: true }));
app.get("/auth/google", async (_, res, next) => { try { res.redirect(await calendar.authorizationUrl()); } catch (e) { next(e); } });
app.get("/oauth2/callback", async (req, res, next) => { try {
  const code = z.string().min(1).parse(req.query.code); await calendar.saveAuthorization(code);
  res.send("Google Calendar connected. You can close this window.");
} catch (e) { next(e); } });

app.get("/agenda", async (req, res, next) => { try {
  const date = z.string().regex(/^\d{4}-\d{2}-\d{2}$/).parse(req.query.date ?? new Date().toISOString().slice(0, 10));
  const start = new Date(`${date}T00:00:00`).toISOString(); const end = new Date(`${date}T23:59:59.999`).toISOString();
  res.json(await calendar.agenda(start, end));
} catch (e) { next(e); } });
app.get("/briefing", async (req, res, next) => { try {
  const date = z.string().regex(/^\d{4}-\d{2}-\d{2}$/).parse(req.query.date ?? new Date().toISOString().slice(0, 10));
  const start = new Date(`${date}T00:00:00`).toISOString(), end = new Date(`${date}T23:59:59.999`).toISOString();
  const events = await calendar.agenda(start, end);
  res.json(agendaBriefing(events, scheduleHealth(events, new Date(start), new Date(end))));
} catch (e) { next(e); } });
app.get("/schedule-health", async (req, res, next) => { try {
  const q = z.object({ start: z.string().datetime({ offset: true }), end: z.string().datetime({ offset: true }) }).parse(req.query);
  res.json(scheduleHealth(await calendar.agenda(q.start, q.end), new Date(q.start), new Date(q.end)));
} catch (e) { next(e); } });

app.get("/free-slots", async (req, res, next) => { try {
  const q = availabilityQuerySchema.parse(req.query);
  const calendars = q.calendars?.split(",").map(x => x.trim()).filter(Boolean) ?? ["primary"];
  res.json(findFreeSlots(await calendar.availability(q.start, q.end, calendars), new Date(q.start), new Date(q.end), q.minutes));
} catch (e) { next(e); } });
app.post("/events", async (req, res, next) => { try { res.status(201).json(await calendar.create(eventSchema.parse(req.body))); } catch (e) { next(e); } });
app.patch("/events/:id", async (req, res, next) => { try { res.json(await calendar.update(req.params.id, eventPatchSchema.parse(req.body))); } catch (e) { next(e); } });
app.delete("/events/:id", async (req, res, next) => { try { await calendar.remove(req.params.id); res.status(204).end(); } catch (e) { next(e); } });

const chatTools: OpenAI.Chat.Completions.ChatCompletionTool[] = [
  { type: "function", function: { name: "get_agenda", description: "Get calendar events in an ISO-8601 time range.", parameters: { type: "object", properties: { start: { type: "string" }, end: { type: "string" } }, required: ["start", "end"], additionalProperties: false } } },
  { type: "function", function: { name: "find_free_slots", description: "Find open blocks and overlapping events in a time range. Add attendee email calendar IDs only when the user asks and has access.", parameters: { type: "object", properties: { start: { type: "string" }, end: { type: "string" }, minutes: { type: "number" }, calendars: { type: "array", items: { type: "string" } } }, required: ["start", "end", "minutes"], additionalProperties: false } } },
  { type: "function", function: { name: "create_event", description: "Create a Calendar event only after the user has supplied all important details and explicitly asked to create it.", parameters: { type: "object", properties: { summary: { type: "string" }, start: { type: "string" }, end: { type: "string" }, description: { type: "string" }, location: { type: "string" }, conference: { type: "boolean" }, recurrence: { type: "array", items: { type: "string" } }, colorId: { type: "string" }, attendees: { type: "array", items: { type: "object", properties: { email: { type: "string" }, optional: { type: "boolean" } }, required: ["email"], additionalProperties: false } } }, required: ["summary", "start", "end"], additionalProperties: false } } },
  { type: "function", function: { name: "update_event", description: "Update a known event ID only after explicit confirmation.", parameters: { type: "object", properties: { id: { type: "string" }, patch: { type: "object" } }, required: ["id", "patch"], additionalProperties: false } } },
  { type: "function", function: { name: "delete_event", description: "Delete a known event ID only after explicit confirmation.", parameters: { type: "object", properties: { id: { type: "string" } }, required: ["id"], additionalProperties: false } } }
];

app.post("/chat", async (req, res, next) => { try {
  if (!config.OPENAI_API_KEY) throw new Error("OPENAI_API_KEY is required for /chat.");
  const message = z.object({ message: z.string().min(1) }).parse(req.body).message;
  const ai = new OpenAI({ apiKey: config.OPENAI_API_KEY });
  const messages: OpenAI.Chat.Completions.ChatCompletionMessageParam[] = [
    { role: "system", content: "You are Calendar Copilot. Use tools for calendar facts. Never create, update, or delete an event until the user has explicitly requested that exact action. Ask concise questions when essential details are missing. State all times with offsets." },
    { role: "user", content: message }
  ];
  for (let i = 0; i < 4; i++) {
    const completion = await ai.chat.completions.create({ model: config.OPENAI_MODEL, messages, tools: chatTools, tool_choice: "auto" });
    const reply = completion.choices[0]?.message;
    if (!reply) throw new Error("The language model returned no response.");
    messages.push(reply);
    if (!reply.tool_calls?.length) return res.json({ message: reply.content ?? "" });
    for (const call of reply.tool_calls) {
      const args = JSON.parse(call.function.arguments) as Record<string, unknown>;
      let result: unknown;
      if (call.function.name === "get_agenda") result = await calendar.agenda(String(args.start), String(args.end));
      else if (call.function.name === "find_free_slots") { const events = await calendar.availability(String(args.start), String(args.end), Array.isArray(args.calendars) ? args.calendars.map(String) : undefined); result = findFreeSlots(events, new Date(String(args.start)), new Date(String(args.end)), Number(args.minutes)); }
      else if (call.function.name === "create_event") result = await calendar.create(eventSchema.parse(args));
      else if (call.function.name === "update_event") result = await calendar.update(String(args.id), eventPatchSchema.parse(args.patch));
      else if (call.function.name === "delete_event") { await calendar.remove(String(args.id)); result = { deleted: true }; }
      else result = { error: "Unknown tool" };
      messages.push({ role: "tool", tool_call_id: call.id, content: JSON.stringify(result) });
    }
  }
  throw new Error("The agent exceeded its action limit.");
} catch (e) { next(e); } });

app.use((err: Error, _: express.Request, res: express.Response, __: express.NextFunction) => {
  console.error(err.message); res.status(400).json({ error: err.message });
});
app.listen(config.PORT, () => console.log(`Calendar Copilot listening on http://localhost:${config.PORT}`));
