# Specification

## 1. Product

A personal calendar that someone can run on their own server with one `docker compose up`. It should feel like a small, fast, focused alternative to Google Calendar for one person's own schedule, and work equally well in a desktop browser and on a phone without installing anything from an app store.

The people who will use it:

- **The self-hoster** installs it on a home server or VPS, usually behind a reverse proxy that terminates HTTPS. They expect sane defaults, configuration through environment variables, one volume to back up, and images for both amd64 and arm64.
- **The user** is the self-hoster and maybe a few family members or friends. Each has their own account and their own calendars. They mostly look at their week on a laptop and check or add things from a phone.

### In scope

- Accounts: first-run setup creates the admin; the admin invites further users; optional open registration
- Password login, optional TOTP with recovery codes, optional OIDC login, personal API tokens
- Multiple calendars per user, each with a colour, each can be hidden
- Events with title, start and end, all-day flag, time zone, location, description, optional own colour, coloured tags
- Recurring events with exceptions, edited as "this event", "this and following" or "all events"
- Reminders delivered by Web Push and by e-mail
- Views: month, week, day, agenda
- Drag and drop to move and resize, quick create by clicking or dragging on the grid, search
- ICS: import a file, export a calendar, a secret read-only feed URL per calendar, and read-only subscriptions to external ICS URLs
- PWA: installable, and already-loaded data stays readable offline
- English UI built on i18n so that other languages can be added by dropping in a file
- Light and dark theme

### Out of scope

Do not build these, and do not add hooks or abstractions in anticipation of them:

- Sharing calendars or events between users
- CalDAV, and two-way sync with Google or Microsoft
- Attendees, invitations, RSVP
- Tasks and to-dos
- Any AI or LLM feature
- Creating or editing while offline
- Year view, and a separate management page for recurring series
- Native mobile apps
- Databases other than SQLite

## 2. Architecture

```
            Browser / installed PWA
                     │ HTTPS (reverse proxy, not part of the image)
                     ▼
┌──────────────────────────────────────────────┐
│ One container, one process (uvicorn)         │
│                                              │
│  FastAPI                                     │
│   ├─ /api/v1/*      REST API (JSON)          │
│   ├─ /feeds/*.ics   public ICS feeds         │
│   ├─ /*             built Vue SPA (static)   │
│   └─ background loop (asyncio task)          │
│        ├─ send due reminders                 │
│        ├─ refresh ICS subscriptions          │
│        └─ nightly cleanup                    │
│                                              │
│  SQLite file in /data  (WAL mode)            │
└──────────────────────────────────────────────┘
        │                │              │
     SMTP server    Push services    External ICS URLs
     (optional)     (FCM, APNs,      (subscriptions)
                     Mozilla)
```

### Decisions and their reasons

**One image, one process.** A self-hoster should not have to run a database, a queue, and a worker for a personal calendar. FastAPI serves the built frontend, and the background jobs run as an asyncio task started in the app's lifespan. The consequence is that the app must run with exactly one uvicorn worker, because two processes would both send every reminder. State this in the README and do not add a `--workers` option.

**SQLite with sync SQLAlchemy.** The data is small and the load is a handful of users. Sync sessions used from FastAPI's threadpool are simpler and less error-prone than the async driver, which is a thread wrapper around the same library anyway. Set these pragmas on every connection: `journal_mode=WAL`, `foreign_keys=ON`, `busy_timeout=5000`, `synchronous=NORMAL`. Alembic migrations run automatically when the container starts, so upgrading is just pulling a new image.

**The server owns time.** Recurrence expansion, time zone conversion and reminder timing are all done in Python, in one place, with `zoneinfo` and `python-dateutil`. Three consumers need the same answer (the API, the reminder scheduler, the ICS export), and a second implementation in the browser would drift from it. The frontend receives ready-made occurrences. Details in section 5.

**REST with a generated TypeScript client.** Two languages means types can drift. FastAPI publishes an OpenAPI schema; `openapi-typescript` turns it into types and `openapi-fetch` gives a typed client. CI fails if the generated file is out of date. The same API serves the SPA (session cookie) and API tokens (Bearer header), so there is no separate "public API" to maintain.

**FullCalendar for the grid, own components for everything else.** The owner wants a specific look (section 11, "Visual design") built with Tailwind. Time grids with drag, resize, overlap layout and touch support are a large amount of fiddly work to get right, and FullCalendar's MIT-licensed core (daygrid, timegrid, list, interaction) does it well. Restyle it with CSS variables and Tailwind so it matches the rest of the app. Do not use any of its premium plugins. Do not use its RRule plugin, since the server expands recurrences. Dialogs, popovers, menus, selects and other interactive primitives are built on Reka UI (unstyled, accessible) and styled with Tailwind.

**Server-side sessions, not JWTs.** Sessions are rows in the database, so a user can see their devices and revoke one, and logging out actually ends the session.

## 3. Repository layout

```
branding.json            app name, short name, description, theme colour
Dockerfile
docker-compose.yml       example deployment
justfile
backend/
  pyproject.toml, uv.lock
  alembic/
  app/
    main.py              app factory, lifespan, static file serving
    config.py            settings from environment (pydantic-settings)
    db.py
    models/              SQLAlchemy models
    schemas/             Pydantic request and response models
    api/                 routers, one module per resource
    services/            business logic
      recurrence.py      expansion and edit-scope operations
      ics.py             parse and serialise iCalendar
      subscriptions.py
      reminders.py
      notify/            push.py, email.py
      auth/              passwords, sessions, totp, oidc, tokens
    scheduler.py         the background loop
    cli.py               admin commands (reset-password, disable-totp, make-admin)
    locales/en.json      texts for e-mails and push notifications
  tests/
frontend/
  package.json, pnpm-lock.yaml
  src/
    api/                 generated schema, typed client, query hooks
    components/
    views/
    stores/              Pinia, UI state only
    locales/en.json
    sw.ts                service worker
  e2e/                   Playwright
docs/
.github/workflows/
```

## 4. Data model

Integer primary keys. Every timestamp column whose name ends in `_utc` holds UTC. All tables that hold user data carry `user_id` directly or reach it through one foreign key, and deleting a user cascades to everything they own.

**users**: `email` (unique, stored lowercased), `display_name`, `password_hash` (null for accounts that only use OIDC), `is_admin`, `is_active`, `timezone` (IANA name), `locale`, `week_start` (monday or sunday), `time_format` (12 or 24), `default_view`, `theme` (system, light, dark), `email_reminders_enabled` (default false), `totp_secret_encrypted`, `totp_enabled_at_utc`, `totp_last_step`, `oidc_issuer`, `oidc_subject` (unique together).

**recovery_codes**: `user_id`, `code_hash`, `used_at_utc`.

**sessions**: `token_hash`, `user_id`, `auth_method` (password or oidc), `created_at_utc`, `last_seen_at_utc`, `expires_at_utc`, `user_agent`, `ip`.

**api_tokens**: `user_id`, `name`, `token_hash`, `token_prefix` (shown in the UI so the user can tell tokens apart), `scope` (read or write), `expires_at_utc` (nullable), `last_used_at_utc`, `revoked_at_utc`.

**invites**: `token_hash`, `email` (optional), `created_by`, `expires_at_utc`, `used_at_utc`. The same mechanism with a `purpose` column serves password reset links. An invite link is valid for 7 days and a reset link for 24 hours; each works once.

**calendars**: `user_id`, `name`, `color`, `kind` (local or subscription), `is_visible`, `sort_order`, `feed_token` (nullable, unique), `default_reminder_minutes` (nullable).

**calendar_subscriptions** (one-to-one with a calendar of kind subscription): `source_url`, `refresh_interval_minutes`, `etag`, `last_modified`, `last_fetched_at_utc`, `next_fetch_at_utc`, `last_status`, `last_error`.

**events**:

| Column | Notes |
| --- | --- |
| `calendar_id` | |
| `uid` | iCalendar UID. Generated for new events, preserved on import. Unique per calendar together with `original_start`. |
| `title`, `description`, `location` | |
| `color` | Nullable. Overrides the calendar colour. |
| `all_day` | |
| `start_local`, `end_local` | Wall-clock time without a zone. `end_local` is exclusive. For all-day events both are at midnight. |
| `timezone` | IANA name. Null for all-day events, which are floating. |
| `start_utc`, `end_utc` | Derived from the three columns above. Indexed for range queries. |
| `rrule` | RFC 5545 RRULE string, null for non-recurring events. |
| `exdates` | JSON list of excluded local start times. |
| `series_end_utc` | Derived. End of the last occurrence, null if the rule never ends. Lets range queries skip finished series. |
| `recurring_event_id` | Set on override rows, points at the master event. |
| `original_start` | Set on override rows: the local start of the occurrence being replaced (RECURRENCE-ID). |
| `sequence`, `created_at_utc`, `updated_at_utc` | |

**tags**: `user_id`, `name` (unique per user, compared case-insensitively), `color`. **event_tags**: join table. A tag is created the first time its name is used and stays until the user deletes it, so that its colour survives periods when no event carries it.

**reminders**: `event_id` (always a master or a single event, never an override), `minutes_before`, `next_fire_at_utc` (indexed, null when nothing is left to fire), `next_occurrence_start`.

**push_subscriptions**: `user_id`, `endpoint` (unique), `p256dh`, `auth`, `user_agent`, `last_success_at_utc`.

**notification_log**: `reminder_id`, `occurrence_start`, `channel`, `status`, `error`, `attempts`, `sent_at_utc`. Unique on the first three columns.

**settings**: key and value. Holds instance settings an admin can change at runtime (open registration) and generated secrets (VAPID keys).

**events_fts**: an FTS5 virtual table over title, description, location and tag names. See section 9.

## 5. Time, recurrence and occurrences

This is the hard part of any calendar and where bugs will come from. Build it carefully and test it harder than anything else.

### Storing time

A timed event stores what the user meant: a wall-clock time and a zone ("9:00 in Europe/Prague"). The UTC columns are derived and exist for querying. This matters for recurrence: a weekly 9:00 meeting must stay at 9:00 local time across a daylight saving change, which means the rule has to be expanded in local time and each occurrence converted to UTC on its own.

New events take the zone from the user's profile. The event editor shows the zone in a collapsed "more options" area where it can be changed. Most users will never touch it.

All-day events have no zone. A birthday on 3 May is on 3 May wherever the user is. Store the end as exclusive (a one-day event on 3 May ends on 4 May), which is also what iCalendar does. The UI shows and edits an inclusive end date. Convert at the edge of the UI and nowhere else.

A wall-clock time that does not exist (inside the spring-forward gap) moves forward by the size of the gap. An ambiguous one (autumn fall-back) takes the first occurrence.

### Expanding recurrences

`services/recurrence.py` exposes one function that everything else uses: given events and a UTC range, return the occurrences in that range. It expands `rrule` with `dateutil.rrule` from the naive local start, removes `exdates`, replaces occurrences that have an override row, and converts each result to UTC through the event's zone.

Guard against pathological input. A query range may not exceed 400 days, and one event may not produce more than 1000 occurrences in one query. Imported rules can be anything.

An occurrence has an id the client can send back: the event id for a single event, and `{master_id}_{original local start as YYYYMMDDTHHMMSS}` for an instance of a series.

### Editing a series

Every update and delete on a recurring event carries a scope.

- **this**: Updating creates an override row linked to the master with `original_start` set. Deleting adds the occurrence's start to the master's `exdates`, and removes its override row if there was one.
- **following**: Split the series. The master's rule gets an `UNTIL` just before the chosen occurrence. A new master starts at the chosen occurrence with the changes applied; if the original rule used `COUNT`, the new one gets the remaining count. Deleting with this scope only truncates. Overrides and exdates at or after the split move to the new master if the edit did not touch start time, duration or rule, and are dropped if it did.
- **all**: Update or delete the master. If the edit changes start time, duration, zone or rule, drop all overrides and exdates, because they can no longer be matched to occurrences. Otherwise keep them.

Dragging an occurrence of a series in the grid asks for the scope, the same as editing it in the form.

### What the recurrence editor offers

Presets generated from the event's start date: does not repeat, daily, every weekday, weekly on that weekday, monthly on that day of the month, monthly on that nth weekday, yearly. Plus a custom option: interval, unit, weekdays for weekly rules, and an end (never, on a date, after a number of occurrences).

Imported events may carry rules the editor cannot represent. The server still expands them correctly because dateutil implements the whole RFC. The editor shows such a rule as a readable summary marked as custom, and lets the user keep it or replace it.

### The occurrences endpoint and the frontend

`GET /api/v1/occurrences?start=…&end=…&tz=…` is what every view loads. For each occurrence it returns the UTC instants and also the wall-clock start and end in the requested display zone, as ISO strings without an offset.

The frontend passes those wall-clock strings to FullCalendar, configured with the same named zone and no time zone plugin. In that mode FullCalendar treats the values as already being in the display zone and does no conversion, and after a drag it hands back wall-clock values in that zone. The client sends them to the server together with the display zone, and the server converts them into the event's own zone. The browser never needs a time zone database. If a FullCalendar upgrade changes this behaviour, keep the principle (the server converts, the client passes wall-clock values through) and adapt the wiring.

The display zone is the one in the user's profile. If the device's zone differs from it (the user is travelling), show a dismissible banner offering to switch.

## 6. Authentication and accounts

### First run and accounts

When the database has no users, the app shows a setup screen that creates the admin. When `APP_PASSWORD_LOGIN_ENABLED` is false, the setup screen offers the OIDC button in place of the password form, and the first user to sign in through it becomes the admin, regardless of `APP_OIDC_AUTO_PROVISION`. After that, accounts come from three places: an invite link created by an admin (sent by e-mail when SMTP is configured, otherwise shown for copying), self-registration if an admin has switched it on, or OIDC auto-provisioning if configured.

The admin area lists users and can invite, deactivate or reactivate, delete, grant or revoke admin rights, produce a password reset link, and reset a user's TOTP. Admins do not create accounts by hand or set other users' passwords. It also shows instance status: version, whether SMTP, OIDC and push are configured, and a button to send a test e-mail. An admin cannot see other users' calendars.

There can be several admins. Two guards, enforced on the server and reflected in the UI by disabled controls:

- The instance always keeps at least one active admin: the last one cannot be demoted, deactivated or deleted.
- Admins cannot revoke their own admin rights or deactivate or delete their own account from the admin area, so nobody locks themselves out by accident.

Deactivating a user or revoking admin rights takes effect immediately: deactivating deletes the user's sessions and their API tokens stop working, and admin checks read the current flag on every request. A deactivated account cannot log in by password or through OIDC, and its API tokens are refused.

Password reset goes by e-mail when SMTP is configured. Without SMTP, the login page says to ask the administrator, who can generate a link. For a locked-out admin: `docker exec <container> python -m app.cli reset-password <email>`. The CLI can also disable TOTP for a user (`disable-totp`) and promote a user to admin (`make-admin`).

### Passwords and sessions

Hash with Argon2id (`argon2-cffi`). Minimum length 10, no composition rules.

A session is a random 32-byte token in an `HttpOnly`, `SameSite=Lax` cookie, marked `Secure` whenever `APP_BASE_URL` is https. Store only its SHA-256 hash. Sessions slide on use, up to `APP_SESSION_DAYS` (default 180). Settings lists active sessions and lets the user revoke each one. Changing the password revokes all other sessions.

For requests authenticated by cookie, reject any state-changing method whose `Origin` (or `Sec-Fetch-Site`) shows it came from another site. Requests authenticated by a Bearer token skip this check.

Throttle failed logins per account and per IP with an in-memory counter and growing delays. Login and reset responses must not reveal whether an e-mail address has an account.

### TOTP

Optional, and each user decides for themselves. Enrolment shows a QR code and the secret, and completes only after the user enters a valid code. It then shows 10 recovery codes once; store only their hashes. Each recovery code works once.

Login becomes two steps: the password yields a short-lived pending token (5 minutes) that can only be exchanged, together with a TOTP or recovery code, for a session. Accept the previous and next time step to tolerate clock drift, and store the last accepted step so a code cannot be replayed. Turning TOTP off requires the password and a current code.

Encrypt the TOTP secret at rest with a key derived from `APP_SECRET_KEY`. A login through OIDC does not ask for TOTP, because second factors are then the identity provider's job.

### OIDC

One generic provider configured by discovery URL, using the authorization code flow with PKCE (`Authlib`) and the scopes `openid email profile`. The login page shows a button labelled with `APP_OIDC_PROVIDER_NAME` when OIDC is enabled.

Resolving who is logging in, in this order:

1. A user already linked to this issuer and subject logs in.
2. Otherwise, if the provider says the e-mail is verified and a local user has that e-mail, link the two and log in.
3. Otherwise, if `APP_OIDC_AUTO_PROVISION` is true, create the user, even when registration is closed.
4. Otherwise refuse with a message that the account has to be created by an administrator first.

Never link on an unverified e-mail: that would let anyone who can set an arbitrary e-mail at the provider take over an account. A logged-in user can also link and unlink their OIDC identity in settings. Unlinking is refused if it would leave the account with no way to log in. `APP_PASSWORD_LOGIN_ENABLED=false` hides the password form for instances that want OIDC only, and is refused at startup unless OIDC is configured.

### API tokens

A user creates named tokens in settings, choosing a scope and an optional expiry. The token is shown once and has a recognisable prefix (`cal_` followed by random characters). Store its SHA-256 hash and the first few characters for display. Clients send it as `Authorization: Bearer …`.

- `read` allows GET requests on calendar data.
- `write` additionally allows creating, changing and deleting calendar data.
- No token can reach account, security or admin endpoints: password, TOTP, sessions, tokens, OIDC linking, user management. Those need a real login.

Settings shows each token's scope, expiry and last use, and can revoke it. The interactive API documentation is served at `/api/docs`.

## 7. Calendars, events and tags

A new user gets one calendar called "Personal". Calendars can be created, renamed, recoloured, reordered, hidden and deleted (deleting asks for confirmation and removes its events). The colour picker offers the fixed palette from section 11.

The sidebar on desktop, a drawer on mobile, lists calendars with a visibility toggle each, then tags as filters. Visibility is saved on the server so it follows the user across devices. Tag filters are a view state and are not saved.

### Tags

Tags are a second, lighter way to group events across calendars ("travel", "kids", "deadline"). Each tag has a name and a colour from the same palette as calendars.

- In the event editor the tag field autocompletes existing tags and creates a new one when the user types an unknown name. A new tag gets the palette colour least used among the user's tags, so the first few tags come out distinct without the user choosing anything.
- The sidebar lists tags with their colour. Clicking one filters the calendar to events carrying it; several selected tags show events carrying any of them. A menu on each tag offers rename, change colour and delete. Deleting a tag removes it from its events and leaves the events alone.
- A tag's colour never changes the colour of an event. An event is drawn in its own colour if it has one, otherwise in its calendar's colour. Tags appear as small colour markers on the event in the week, day and agenda views (at most three, then "+N"), and as labelled chips in the event detail and in search results. The month view is too dense for them and shows none.
- In ICS, tags map to CATEGORIES, which carries only names. Imported names that match an existing tag reuse it; new ones are created with an automatic colour.

Event fields: title, calendar, start and end, all-day, time zone, repeat, reminders, location, description, colour, tags. Location is plain text with a link that opens the system's maps app. The description is plain text; make URLs in it clickable by building links from text, never by injecting HTML. An empty title is saved as "(No title)" via i18n at display time.

Events in subscription calendars are read-only everywhere: no drag, no edit form, a small indicator in the detail view. Enforce it in the service layer as well as in the UI.

## 8. Reminders and notifications

A reminder is an offset before the start of an event. An event can have several. The editor offers common offsets (at start, 5, 10, 15, 30 minutes, 1 hour, 1 day before) and a custom one. For all-day events the choices are times of day on the day itself or the day before (for example "the day before at 18:00"), computed against midnight in the user's zone. A calendar's `default_reminder_minutes` prefills new events in it, including ones made with quick create.

Reminders belong to the master event and apply to each of its occurrences, including ones moved by an override. Subscription calendars have no reminders in this version.

Channels are a per-user choice, not a per-reminder one: push goes to every device the user has subscribed, and e-mail goes out if the user has turned on `email_reminders_enabled` and SMTP is configured.

### Scheduling

Each reminder row keeps `next_fire_at_utc`, the time it should next fire. It is recomputed whenever its event, the event's exceptions, or the reminder itself changes, and after each firing. The background loop wakes every 30 seconds and selects reminders whose time has come. This makes each tick one indexed query rather than an expansion of every event in the database.

For each due reminder:

1. If the occurrence started more than 15 minutes ago, the server was down or the event was edited into the past. Skip it without sending.
2. Otherwise deliver on each of the user's channels, writing to `notification_log`. The unique constraint makes delivery idempotent if the process dies midway.
3. Advance `next_fire_at_utc` to the next occurrence.

A failed delivery is retried on later ticks, up to three attempts.

### Web Push

Use `pywebpush`. Generate the VAPID key pair on first start and keep it in the `settings` table, unless provided by environment. Each device subscribes from a button in settings, which is also where the permission prompt is triggered; browsers require a user gesture, and asking on page load gets permission denied permanently. A push service answering 404 or 410 means the subscription is dead: delete it.

The payload carries a title (the event title), a body (the localised time and location), and the occurrence id. The service worker shows the notification, and tapping it opens that event.

On iPhone and iPad, Web Push only works after the user has added the app to the home screen. Detect iOS Safari running in a browser tab and show instructions for that in place of the subscribe button.

### E-mail

Standard library `smtplib` called from the threadpool, with plain-text and simple HTML parts. Three kinds of mail: reminder, invite, password reset. If SMTP is not configured, every feature depending on it disappears from the UI rather than failing on use.

Texts for push and e-mail are rendered on the server in the recipient's locale and zone, from `backend/app/locales`.

## 9. Search

LIKE in SQLite is only case-insensitive for ASCII and cannot ignore diacritics, which makes it poor for most European languages. Use an FTS5 table with the `unicode61` tokenizer and `remove_diacritics 2`, kept in sync by triggers or by the service layer, and query it with prefix matching so results appear while typing.

Search covers title, description, location and tags across all of the user's calendars, including subscriptions and hidden calendars. A result is an event, not an occurrence. For a recurring event show its next upcoming occurrence, or its last one if the series has ended. Order upcoming results first, nearest first, then past ones, most recent first. Choosing a result navigates the calendar to that date and opens the event.

## 10. ICS

Use the `icalendar` library for parsing and serialising. Everything here maps through the same model: UID, DTSTART and DTEND with TZID or as dates, RRULE, EXDATE, RECURRENCE-ID for overrides, SUMMARY, DESCRIPTION, LOCATION, CATEGORIES for tags, VALARM for reminders (import display alarms with a relative trigger, ignore the rest).

**Import.** The user uploads an `.ics` file and picks a target calendar. Events are matched by UID within that calendar: an existing UID is updated, a new one is created, so importing the same file twice does not duplicate anything. Report how many were created, updated and skipped, with reasons for the skipped ones. One bad event must not fail the whole file. Limit uploads to 10 MB.

**Export.** Download any calendar as an `.ics` file.

**Feed.** A calendar can have a secret URL, `/feeds/{token}.ics`, that serves the same output without login, so the user can add it to Google Calendar, Apple Calendar or a phone. The token is 32 random bytes, can be regenerated (which invalidates the old URL) and can be removed. Off by default. Send `Cache-Control: private, max-age=300`.

**Subscriptions.** The user adds an external ICS URL (accept `webcal://` and treat it as `https://`). It becomes a read-only calendar. The background loop refetches it on its interval (default 60 minutes, minimum 15), sends `If-None-Match` and `If-Modified-Since`, and on new content replaces the calendar's events inside one transaction. If a fetch or parse fails, keep the previous events and record the error; the UI shows the last successful refresh and the error. A manual refresh button exists.

Fetching URLs supplied by users is a server-side request forgery risk. Refuse URLs that resolve to loopback, private, or link-local addresses unless `APP_ALLOW_PRIVATE_SUBSCRIPTION_URLS=true`, check the resolved address on every redirect hop, allow only http and https, and cap the response at 10 MB and the request at 30 seconds.

## 11. Frontend

### Structure

Vue 3 with `<script setup>` and TypeScript in strict mode. TanStack Query holds server state (occurrences, calendars, the current user) and handles caching, invalidation and optimistic updates. Pinia holds UI state only: current date, current view, sidebar state, active tag filters. Moving or resizing an event updates the grid optimistically and rolls back with a toast if the server refuses.

Routes: `/setup`, `/login`, `/invite/:token`, `/reset/:token`, the calendar at `/:view/:date?`, `/event/:occurrenceId` as a deep link that opens the calendar with that event's detail, `/settings/*`, `/admin/*`.

### Layout and views

Design for a phone first, then widen.

**Desktop** (wide viewport): a collapsible sidebar with a mini month for navigation, the calendar list and tag filters; a top bar with today, previous and next, the current range as a title, the view switcher and search. Default view is week.

**Phone** (narrow viewport): no sidebar, a drawer in its place. A compact top bar. A floating button creates an event. Swiping left or right moves to the previous or next range. Default view is agenda.

- **Month**: on desktop, the usual grid with event chips and "+N more". On a phone, the cells show only coloured dots, and the events of the selected day are listed under the grid.
- **Week**: seven days on desktop, three days on a phone.
- **Day**: one day with the time grid.
- **Agenda**: a chronological list grouped by day that loads further into the future as the user scrolls.

The time grid scrolls to the current time on load and shows a line for now. All-day events sit in a strip above the grid.

### Interactions

- **Quick create**: clicking an empty slot, or dragging across a range, opens a small popover with a title field, the time already filled in, and a calendar selector. Enter saves. A "more options" link opens the full editor with what was typed so far. On a phone, tapping a slot or the floating button opens the full editor as a bottom sheet.
- **Event detail**: clicking an event opens a popover (bottom sheet on a phone) with its details and edit and delete actions.
- **Drag and drop**: move between times and days, resize from the bottom edge, drag between the all-day strip and the grid. On touch devices a long press starts the drag, so that scrolling still works.
- **Search**: a field in the top bar (an icon that expands on a phone) with results in a dropdown as the user types.
- **Undo**: after a delete or a move, a toast offers undo for a few seconds.

### Visual design

The owner wants the look of Vercel's design language, in the specific variant used across their other products. It was taken from the stylesheet of one of those products (a contact form) and is now built into the design tokens in `frontend/src/styles/tokens.css` and the shared elements in `ui.css`, which K-Notes uses too. New UI builds on those and should look like it belongs to the same family.

What defines the style:

- **Monochrome first.** Near-black ink on white, near-white on near-black. Greys do the structural work. The accent blue is rare: the primary action, today's date, the current-time line, links. Colour otherwise belongs to the user's calendars and tags, which is what makes them easy to read.
- **Square corners.** Border radius is zero on everything: buttons, inputs, event blocks, dialogs, chips, checkboxes, colour swatches, the floating button. The only round thing is a loading spinner. This is the trait that separates the owner's variant from stock Vercel, so do not soften it.
- **Hairlines, not shadows.** Surfaces are separated by 1 px borders in the line colour. Cards and panels have no shadow and no fill different from the page. Popovers, menus and sheets float above a busy grid, so they get the border plus one soft shadow token; modal dialogs also dim the page behind them.
- **Geist and Geist Mono.** Sans for everything, mono with tabular figures for numbers that should align or read as data: times in the grid gutter and on events, dates in the agenda, counts, token prefixes. Self-host both through their npm font packages. Do not load them from Google Fonts: the app must work offline, under a strict CSP, and without telling a third party who uses it.
- **Small, dense type.** 14 px base, 13 px medium-weight labels in the muted colour, 12 px mono for meta. Headings are weight 600 with slightly negative letter spacing. Nothing heavier than 600.
- **Thin square icons.** Lucide, drawn at stroke width 1.6 with square line caps and mitred joins set globally, so they match the reference's icons.
- **Quiet state changes.** Hover darkens a border or tints the background with a few percent of ink (`color-mix`), and only applies under `(hover: hover) and (pointer: fine)` so that touch devices do not get stuck hover states. Focus shows an ink border with a 3 px translucent ring on inputs, and a 2 px ink outline on buttons and links. Colour transitions take 150 ms. Movement is small (a few pixels) and uses the reference's ease-out curve. Under `prefers-reduced-motion`, movement becomes a fade or nothing.

Tokens. Define these as CSS custom properties using `light-dark()`, with `color-scheme` on the root switched by a `data-theme` attribute, and expose them to Tailwind as theme colours. Components use the tokens only, never raw colour values.

| Token | Light | Dark | Use |
| --- | --- | --- | --- |
| `bg` | `#ffffff` | `#0a0a0a` | Page and surfaces |
| `ink` | `#171717` | `#ededed` | Text, focused borders |
| `muted` | `#666666` | `#a1a1a1` | Secondary text, labels |
| `faint` | `#8f8f8f` | `#8f8f8f` | Meta, placeholders, disabled |
| `line` | `#eaeaea` | `#2e2e2e` | Borders, grid lines |
| `line-hover` | `#c9c9c9` | `#454545` | Hovered borders |
| `accent` | `#1f6fd6` | `#1f6fd6` | Primary action, today, now |
| `accent-hover` | `#1a5fc8` | `#1a5fc8` | |
| `danger` | `#d1242f` | `#ff6369` | Errors, destructive actions |
| `warning` | `#b45309` | `#f5a524` | |
| `success` | `#1a8c3e` | `#3fb950` | |
| `scrim` | black at 30 % | black at 60 % | The dimmed backdrop behind dialogs, sheets and the phone drawer; black in both themes, so it darkens a dark page instead of washing it out |

Applying it to a calendar, which the reference does not cover:

- **Grid.** Hairlines in `line`. Hour labels and day numbers in mono, `faint`. Today is marked by an accent square behind the day number, not by tinting the whole column. The current-time line is 1 px accent. Weekends are not shaded.
- **Events.** A block is a tint of its colour (the colour mixed into `bg` at a low percentage) with a 2 px solid bar of the full colour on its left edge, the title in `ink` and the time in mono `muted`. Not a saturated filled block with white text: tints keep a full week readable and keep the page monochrome at a glance. Past events are dimmed. Events from subscriptions look the same.
- **Palette.** One fixed set of about ten hues serves calendars, per-event colours and tags. Choose values that stay distinguishable from each other and keep the title readable when tinted, in both themes, and check them in both.
- **Tags.** A chip is a small square of the tag's colour followed by its name, inside a hairline border. A marker on an event is the square alone.
- **Controls.** Inputs are 40 px high. Primary buttons are solid accent with white text; secondary buttons are a hairline border on `bg`; destructive actions use `danger` as text or border and are never solid by default. Segmented controls (the view switcher) are joined hairline boxes with the active one inverted to ink on `bg`.
- **Banners** (offline, device zone, errors) follow the reference's notice: a border and a faint tint of one tone colour, with a thin icon.
- **Phone.** Sheets rise from the bottom with square corners and a hairline top border. Tap targets are at least 44 px even where the visual is smaller.

Themes follow the system by default, with light and dark as explicit choices in settings. Every interactive element is reachable and operable from the keyboard, and dialogs trap and restore focus (Reka UI handles most of that).

Dates and times are formatted with `Intl` according to the user's locale and their 12 or 24 hour and week start preferences.

### Internationalisation

All UI text lives in `frontend/src/locales/en.json` and is used through vue-i18n, with plural forms where counts appear. Adding a language must need nothing more than a new JSON file on each side and one entry in a list of available locales. English is the only language shipped. The README explains how to contribute a translation.

## 12. PWA and offline

Use `vite-plugin-pwa` in `injectManifest` mode, because the service worker needs custom code for push. The manifest takes its name, short name and theme colour from `branding.json`. Provide icons including maskable ones and an Apple touch icon. Show an unobtrusive prompt when a new version of the app is available instead of reloading under the user.

Offline is read-only:

- The app shell is precached, so the app opens without a network.
- GET requests for the current user, calendars and occurrences are cached at runtime with a network-first strategy that falls back to the cache.
- While online, the app quietly prefetches occurrences from one month back to three months ahead, so that an offline user has more than the last screen they looked at.
- When offline, show a banner, and disable everything that would write: no drag, no create, no edit buttons. Do not queue writes.

Cached API responses are personal data. Clear all runtime caches on logout, and whenever the app notices that the logged-in user has changed.

Service workers and push need a secure context. That means HTTPS in production (localhost is exempt for development). The README must say this clearly, because an instance served over plain HTTP on a LAN address will work as a website but will not install or send notifications.

## 13. API

Base path `/api/v1`. JSON. Errors have a consistent shape with a machine-readable code and a message. Dates in the API are ISO 8601.

The main resources, as a guide to the shape rather than a complete list:

| Area | Endpoints |
| --- | --- |
| Public | `GET /config` (app name, version, whether first-run setup is still needed, which login methods are enabled, whether registration is open, VAPID public key), `GET /health` |
| Auth | `POST /auth/setup`, `/auth/login`, `/auth/login/totp`, `/auth/logout`, `/auth/register`, `/auth/password-reset/*`, `GET /auth/oidc/login`, `GET /auth/oidc/callback` |
| Account | `GET` and `PATCH /me`, `/me/password`, `/me/totp/*`, `/me/sessions`, `/me/tokens`, `/me/oidc`, `/me/push-subscriptions` |
| Calendars | CRUD on `/calendars`, `/calendars/{id}/feed`, `/calendars/{id}/export`, `/calendars/{id}/import`, `/calendars/{id}/refresh` |
| Events | `GET /occurrences`, `POST /events`, `GET`, `PATCH` and `DELETE /events/{id}` with `scope` and `occurrence` parameters for series |
| Tags | `GET` and `POST /tags`, `PATCH` and `DELETE /tags/{id}` |
| Search | `GET /search?q=` |
| Admin | `/admin/users`, `/admin/invites`, `/admin/settings`, `/admin/status` |

## 14. Configuration

Everything is configured by environment variables with the neutral prefix `APP_`, so a rename of the project does not break deployments. The app must start and be usable with none of them set except `APP_BASE_URL`.

| Variable | Default | Purpose |
| --- | --- | --- |
| `APP_BASE_URL` | none | Public URL of the instance. Required. Used for links in e-mails, invite and reset links, the OIDC redirect, cookie security and origin checks. |
| `APP_DATA_DIR` | `/data` | Database and generated secrets. |
| `APP_SECRET_KEY` | generated | If unset, generated on first start and saved in `APP_DATA_DIR`. |
| `APP_SESSION_DAYS` | `180` | Sliding session lifetime. |
| `APP_TRUSTED_PROXIES` | none | Addresses whose `X-Forwarded-*` headers are believed. |
| `APP_SMTP_HOST`, `APP_SMTP_PORT`, `APP_SMTP_USER`, `APP_SMTP_PASSWORD`, `APP_SMTP_FROM`, `APP_SMTP_SECURITY` | unset | E-mail. `APP_SMTP_SECURITY` is `starttls`, `ssl` or `none`. |
| `APP_OIDC_DISCOVERY_URL`, `APP_OIDC_CLIENT_ID`, `APP_OIDC_CLIENT_SECRET` | unset | Setting these enables OIDC. |
| `APP_OIDC_PROVIDER_NAME` | `SSO` | Label on the login button. |
| `APP_OIDC_AUTO_PROVISION` | `false` | Create accounts for unknown OIDC users. |
| `APP_PASSWORD_LOGIN_ENABLED` | `true` | Set `false` to allow only OIDC. Refused at startup unless OIDC is configured. |
| `APP_VAPID_PUBLIC_KEY`, `APP_VAPID_PRIVATE_KEY` | generated | |
| `APP_VAPID_CONTACT` | derived from `APP_SMTP_FROM` or `APP_BASE_URL` | Contact address sent to push services. |
| `APP_ALLOW_PRIVATE_SUBSCRIPTION_URLS` | `false` | |
| `APP_LOG_LEVEL` | `info` | |

Validate configuration at startup and fail with a message that names the variable and the problem.

## 15. Security

- Authorisation is enforced in one place: a dependency resolves the current user, and service functions take that user and scope every query by it. Section "Conventions" in `CLAUDE.md` requires a cross-user test for every endpoint.
- Send security headers on every response: a Content-Security-Policy that allows scripts and styles only from the app's own origin, images from `self`, `blob:` and `data:`, and connections only to `self`, with `frame-ancestors 'none'`; `X-Content-Type-Options: nosniff`; and `Referrer-Policy: no-referrer`. All fonts and icons are bundled; the app loads nothing from third-party origins. FullCalendar injects its stylesheet at runtime: satisfy the policy with a nonce rather than `unsafe-inline`, and confirm how against the version you install.
- Never render user-supplied or imported text as HTML. Event text from subscriptions is untrusted input from the internet.
- Secrets (session tokens, API tokens, invite and reset tokens, recovery codes) are stored only as hashes and compared in constant time.
- Never log secrets, tokens, passwords or feed URLs.
- The SSRF rules in section 10 apply to every outgoing request to a user-supplied URL.

## 16. Deployment and operations

**Image.** A multi-stage Dockerfile: a Node stage builds the frontend, a slim Python stage installs the backend with `uv` and copies the built assets in. It runs as a non-root user, exposes one port, declares `/data` as a volume, and has a `HEALTHCHECK` against `/api/v1/health`. Keep the image small.

**Startup.** Run migrations, generate any missing secrets, then start uvicorn with one worker.

**Compose.** `docker-compose.yml` in the repository is a working example with the volume and the common variables, with SMTP and OIDC shown commented out. The README adds a short example of putting it behind Caddy for HTTPS.

**Backups and cleanup.** The app does not make backups itself. Backup is stopping the container and copying the data directory; restore is the same in reverse, and the README explains both. Once a night the background loop deletes expired sessions, used or expired invites, and old `notification_log` rows.

**CI.** GitHub Actions. On every push and pull request: lint, type checks and unit tests for both sides, a check that the generated API types are current, a Docker build, and the Playwright suite against that image. On a version tag: build for `linux/amd64` and `linux/arm64` and push to `ghcr.io` under the repository's own name, tagged with the version and `latest`.

**Repository files.** `README.md` (what it is, a screenshot, quick start, configuration table, HTTPS note, backup and restore, admin CLI, how to add a translation, development setup), `LICENSE.md` (MIT), `CONTRIBUTING.md`. There is no changelog file: the notes of each GitHub release are written by hand, in the form given in `CONTRIBUTING.md`.

## 17. Testing

The backend carries most of the testing, because that is where the logic is.

**Backend, pytest.** Use a fresh temporary SQLite database per test and a library that freezes time. Cover every endpoint for the success case, validation errors, the unauthenticated case, and the cross-user case. Recurrence and time get the deepest coverage:

- Daylight saving transitions in both directions, in at least Europe/Prague and America/New_York, for timed series and for reminders
- Monthly rules on the 29th, 30th and 31st, yearly on 29 February, nth-weekday rules
- `COUNT`, `UNTIL`, `INTERVAL`, `EXDATE`, overrides, and overrides that move an occurrence to another day
- Each edit scope, including splitting a series that uses `COUNT` and what happens to later overrides
- All-day events seen from zones far east and far west of UTC, and the exclusive end date
- Range queries at their boundaries: events that span the start or the end of the range, and series that ended before it

Also: ICS round trips (export, import, compare) and a set of fixture files written by Google Calendar, Apple Calendar and Outlook, including malformed input; the reminder scheduler with frozen time, covering late and missed reminders, idempotency and retries, with push and SMTP mocked; the subscription fetcher against a local test server, covering conditional requests, failures and the SSRF rules; the full TOTP, OIDC (against a fake provider) and token scope flows.

**Frontend, Vitest.** Unit tests for logic that lives in the frontend: building and summarising recurrence rules, the inclusive and exclusive all-day conversion, formatting helpers, and the stores. Do not write a test per component.

**End to end, Playwright.** A small suite against the built image, run on a desktop and a phone viewport: first-run setup and login; quick create; full editor with a recurring event, then editing one occurrence and then the whole series; drag to move; search; importing an ICS file; loading the calendar, going offline, and still seeing events with editing disabled.
