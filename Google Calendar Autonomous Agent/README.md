# Calendar Copilot

A personal, natural-language Google Calendar agent. It can brief you on today, manage events and attendees, identify free time, find conflicts, and create recurring or focus-time blocks. Credentials and OAuth tokens stay local and are deliberately excluded from Git.

## What it supports

- Create, update, reschedule, cancel, and delete events
- Invite required or optional guests and automatically request a Google Meet link
- View agendas for any time window, including a daily briefing
- Find uninterrupted availability and flag overlapping events in the connected calendar
- Create events with Google Calendar recurrence rules
- Create native Google Calendar focus-time and out-of-office blocks
- Apply color IDs and private, searchable Copilot tags for batching workflows
- Generate schedule-health metrics: meeting/focus minutes, overlaps, back-to-back meetings, and longest free block
- Correct time-zone handling through RFC 3339 timestamps with UTC offsets

The REST endpoints are usable directly. `POST /chat` additionally lets an OpenAI model choose approved Calendar actions through tool calling.

This first version deliberately scopes itself to Google Calendar. Gmail, Drive, and Google Chat meeting-context search need additional OAuth scopes and separate API enablement, so they are left out rather than requesting broader access by default.

## Setup

1. Create a Google Cloud project, enable **Google Calendar API**, and create an OAuth 2.0 client of type **Web application**.
2. Add `http://localhost:3000/oauth2/callback` as an authorized redirect URI (or match the URI you put in `.env`).
3. Copy `.env.example` to `.env` and add your Google client ID and secret. Add an OpenAI key only if using `/chat`.
4. Install and run:

   ```bash
   npm install
   npm run dev
   ```

5. Open `http://localhost:3000/auth/google`, approve Calendar access, then use the API.

OAuth tokens are stored in `tokens/google-token.json`, which is ignored by Git. For a deployed version, replace this file store with encrypted, access-controlled secret storage.

## Examples

```bash
# Today’s agenda
curl 'http://localhost:3000/agenda?date=2026-09-28'

# Create an event (the API will email invitations)
curl -X POST http://localhost:3000/events \
  -H 'Content-Type: application/json' \
  -d '{"summary":"Project kickoff","start":"2026-09-29T14:00:00-04:00","end":"2026-09-29T14:30:00-04:00","attendees":[{"email":"person@example.com"}],"conference":true}'

# Find a 90-minute free slot
curl 'http://localhost:3000/free-slots?start=2026-09-29T09:00:00-04:00&end=2026-09-29T17:00:00-04:00&minutes=90'

# Natural language (requires OPENAI_API_KEY)
curl -X POST http://localhost:3000/chat -H 'Content-Type: application/json' \
  -d '{"message":"What is on my agenda today?"}'

# Create protected focus time with a private project tag
curl -X POST http://localhost:3000/events -H 'Content-Type: application/json' \
  -d '{"summary":"Write launch plan","start":"2026-09-30T09:00:00-04:00","end":"2026-09-30T11:00:00-04:00","eventType":"focusTime","colorId":"11","tags":{"project":"launch"}}'
```

## API

| Method | Route | Purpose |
|---|---|---|
| GET | `/auth/google` | Begin Google OAuth consent |
| GET | `/oauth2/callback` | OAuth callback; saves token locally |
| GET | `/agenda?date=YYYY-MM-DD` | Events for a local calendar day |
| GET | `/briefing?date=YYYY-MM-DD` | Agenda plus a concise schedule-health briefing |
| GET | `/schedule-health?start=&end=` | Workload, focus, conflict, and buffer metrics |
| GET | `/free-slots?start=&end=&minutes=&calendars=` | Contiguous openings and conflicts; pass accessible calendar IDs/emails comma-separated |
| POST | `/events` | Create an event, invitees, Meet link, recurrence |
| PATCH | `/events/:id` | Modify/reschedule an event |
| DELETE | `/events/:id` | Delete an event and notify guests |
| POST | `/chat` | Natural-language tool-using agent |

## Security and privacy

- Never commit `.env`, OAuth tokens, keys, or real attendee data.
- This app requests only `calendar` scope. Reduce it to `calendar.events` if read-only agendas are not required.
- Google sends invitations only when `sendUpdates: "all"` is selected, as this project does for explicit create/update/delete actions.
- The optional LLM route receives the user’s request and only the Calendar data needed to answer it. Use a trusted model/provider and do not expose the server publicly without authentication.
- Review the Google OAuth consent screen and any Workspace admin policies before using this with a work account.

## Development

Run `npm run test:offline` before connecting Google. It type-checks the app and runs unit tests for time ranges, overlapping events, free slots, recurrence, attendee email validation, and invalid/reversed date ranges; it never calls Google or OpenAI. See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution expectations.

Update requests are strict: changing `eventType` is rejected because Google Calendar does not allow an existing event’s type to change, and unknown fields are rejected to prevent silently ignored edits.

GitHub Actions also runs that offline suite and a scheduled CodeQL scan. CodeQL supports JavaScript/TypeScript analysis, while Dependabot tracks dependency updates. [GitHub’s CodeQL documentation](https://docs.github.com/en/code-security/concepts/code-scanning/codeql/codeql-code-scanning) and [Google’s event-type documentation](https://developers.google.com/workspace/calendar/api/guides/event-types) describe these integrations.
