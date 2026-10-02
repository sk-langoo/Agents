# Architecture

```
Browser or API client
        │
        ▼
Express API ── optional natural-language route ── OpenAI tool calling
        │                                             │
        └──────────── CalendarService ◀───────────────┘
                         │
                         ▼
                 Google Calendar API
                         │
                local OAuth token file
                (Git-ignored, mode 0600)
```

The language model has no direct Google credential. It can only invoke the limited calendar operations defined in `src/index.ts`. Mutating operations require the user’s explicit instruction in the system prompt; production deployments should add application authentication, audit logging, a confirmation UI, and encrypted token storage.

## Design notes

- All date-time inputs use RFC 3339 strings with UTC offsets, avoiding silent time-zone conversion errors.
- Google Calendar availability uses `freebusy.query`. It can compare the primary calendar with calendar IDs/emails that the connected account is permitted to see.
- The planning module is deterministic and credential-free, making its schedule-health heuristics fast to test offline.
- Copilot tags are stored as private Google Calendar extended properties, with a `copilot_` prefix. Private properties stay on the connected account’s event copy rather than being shared with guests.
- Google Meet links are requested with `conferenceDataVersion: 1` whenever `conference` is true.
- Recurrence uses Google Calendar’s `RRULE` strings, for example `RRULE:FREQ=WEEKLY;BYDAY=MO`.
