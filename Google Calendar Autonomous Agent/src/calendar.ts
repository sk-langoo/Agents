import { google, calendar_v3 } from "googleapis";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { config, requireGoogleConfig } from "./config.js";

const TOKEN_PATH = path.resolve("tokens/google-token.json");
const SCOPE = "https://www.googleapis.com/auth/calendar";

export type Attendee = { email: string; optional?: boolean };
export type CreateEvent = {
  summary: string; start: string; end: string; description?: string; location?: string;
  attendees?: Attendee[]; conference?: boolean; recurrence?: string[]; colorId?: string;
  eventType?: "default" | "focusTime" | "outOfOffice"; tags?: Record<string, string>;
};

export class CalendarService {
  private oauth() {
    requireGoogleConfig();
    return new google.auth.OAuth2(config.GOOGLE_CLIENT_ID, config.GOOGLE_CLIENT_SECRET, config.GOOGLE_REDIRECT_URI);
  }

  async authorizationUrl() {
    const oauth = this.oauth();
    return oauth.generateAuthUrl({ access_type: "offline", prompt: "consent", scope: [SCOPE] });
  }

  async saveAuthorization(code: string) {
    const oauth = this.oauth();
    const { tokens } = await oauth.getToken(code);
    await mkdir(path.dirname(TOKEN_PATH), { recursive: true });
    await writeFile(TOKEN_PATH, JSON.stringify(tokens, null, 2), { mode: 0o600 });
  }

  private async client(): Promise<calendar_v3.Calendar> {
    const oauth = this.oauth();
    try { oauth.setCredentials(JSON.parse(await readFile(TOKEN_PATH, "utf8"))); }
    catch { throw new Error("Google Calendar is not connected. Visit /auth/google first."); }
    return google.calendar({ version: "v3", auth: oauth });
  }

  async agenda(start: string, end: string) {
    const api = await this.client();
    const { data } = await api.events.list({ calendarId: "primary", timeMin: start, timeMax: end, singleEvents: true, orderBy: "startTime" });
    return data.items ?? [];
  }

  async availability(start: string, end: string, calendars: string[] = ["primary"]) {
    const api = await this.client();
    const { data } = await api.freebusy.query({ requestBody: { timeMin: start, timeMax: end, items: calendars.map(id => ({ id })) } });
    return Object.entries(data.calendars ?? {}).flatMap(([calendar, value]) =>
      (value.busy ?? []).map(block => ({ calendar, start: { dateTime: block.start }, end: { dateTime: block.end } }))
    );
  }

  async create(input: CreateEvent) {
    const api = await this.client();
    const { data } = await api.events.insert({
      calendarId: "primary", sendUpdates: "all", conferenceDataVersion: input.conference ? 1 : 0,
      requestBody: {
        summary: input.summary, description: input.description, location: input.location, colorId: input.colorId,
        start: { dateTime: input.start }, end: { dateTime: input.end }, recurrence: input.recurrence,
        attendees: input.attendees?.map(a => ({ email: a.email, optional: a.optional ?? false })), eventType: input.eventType,
        focusTimeProperties: input.eventType === "focusTime" ? { autoDeclineMode: "declineNone" } : undefined,
        outOfOfficeProperties: input.eventType === "outOfOffice" ? { autoDeclineMode: "declineNone" } : undefined,
        extendedProperties: input.tags ? { private: Object.fromEntries(Object.entries(input.tags).map(([key, value]) => [`copilot_${key.slice(0, 36)}`, value.slice(0, 1024)])) } : undefined,
        conferenceData: input.conference ? { createRequest: { requestId: crypto.randomUUID() } } : undefined
      }
    });
    return data;
  }

  async update(id: string, patch: Partial<CreateEvent>) {
    const api = await this.client();
    const { tags, attendees, start, end, ...fields } = patch;
    const { data } = await api.events.patch({
      calendarId: "primary", eventId: id, sendUpdates: "all",
      requestBody: {
        ...fields,
        start: start ? { dateTime: start } : undefined,
        end: end ? { dateTime: end } : undefined,
        attendees: attendees?.map(a => ({ email: a.email, optional: a.optional ?? false })),
        extendedProperties: tags ? { private: Object.fromEntries(Object.entries(tags).map(([key, value]) => [`copilot_${key.slice(0, 36)}`, value.slice(0, 1024)])) } : undefined
      }
    });
    return data;
  }

  async remove(id: string) {
    const api = await this.client();
    await api.events.delete({ calendarId: "primary", eventId: id, sendUpdates: "all" });
  }
}

export function findFreeSlots(events: calendar_v3.Schema$Event[], start: Date, end: Date, minimumMinutes: number) {
  const busy = events
    .map(e => ({ start: new Date(e.start?.dateTime ?? e.start?.date ?? ""), end: new Date(e.end?.dateTime ?? e.end?.date ?? "") }))
    .filter(e => !Number.isNaN(+e.start) && !Number.isNaN(+e.end))
    .sort((a, b) => +a.start - +b.start);
  const slots: { start: string; end: string; minutes: number }[] = [];
  const conflicts: { start: string; end: string }[] = [];
  let cursor = start;
  for (const item of busy) {
    if (item.start < cursor && item.end > cursor) conflicts.push({ start: item.start.toISOString(), end: item.end.toISOString() });
    if (item.start > cursor) {
      const minutes = Math.floor((+item.start - +cursor) / 60000);
      if (minutes >= minimumMinutes) slots.push({ start: cursor.toISOString(), end: item.start.toISOString(), minutes });
    }
    if (item.end > cursor) cursor = item.end;
  }
  const tail = Math.floor((+end - +cursor) / 60000);
  if (tail >= minimumMinutes) slots.push({ start: cursor.toISOString(), end: end.toISOString(), minutes: tail });
  return { slots, conflicts };
}
