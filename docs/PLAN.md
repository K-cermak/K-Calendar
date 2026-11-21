# Build plan

Work through the milestones in order. Each one ends with something that runs and can be tried. Tick a box when the item is built, tested and committed. Stop after each milestone and report: what was built, what was verified and how, anything that deviates from `SPEC.md`, and open questions. Do not start the next milestone until the owner confirms. Section numbers refer to `SPEC.md`.

A milestone is done when:

- `just check` passes
- the Docker image builds and the app in it starts
- each acceptance point has been tried in the running app, not only in tests
- its boxes here are ticked

The database schema for events includes the recurrence columns from Milestone 2 onward, even though recurrence is built in Milestone 4. Adding them later would mean rewriting the range queries.

---

## Milestone 0: Skeleton

Sections 2, 3, 16.

- [x] `git init`, `.gitignore`, `LICENSE` (MIT), `branding.json`
- [x] Backend project with `uv`: FastAPI app factory, settings, SQLite connection with the pragmas from section 2, Alembic, `GET /api/v1/health`
- [x] Frontend project with `pnpm`: Vite, Vue 3, TypeScript strict, Tailwind, Vue Router, Pinia, TanStack Query, vue-i18n with `en.json`
- [x] Design foundation from section 11 "Visual design": colour tokens with `light-dark()` exposed to Tailwind, self-hosted Geist and Geist Mono, zero radius, global icon stroke settings, and the base controls (button variants, input, checkbox, segmented control, notice) on a throwaway showcase route
- [x] Typed API client generated from the OpenAPI schema (`just api-types`)
- [x] Lint, format and type checking for both sides (ruff and pyright for Python; ESLint, Prettier and `vue-tsc` for the frontend)
- [x] `justfile` with the commands listed in `CLAUDE.md`
- [x] Multi-stage `Dockerfile` and `docker-compose.yml`; FastAPI serves the built SPA with a fallback to `index.html` for client routes
- [x] GitHub Actions workflow that runs `just check` and builds the image
- [x] Update the Commands section of `CLAUDE.md` if anything differs

**Acceptance:** `docker compose up` serves a placeholder page that calls the health endpoint through the typed client and shows the result. The showcase route, put next to the owner's reference form in light and in dark, reads as the same design family. CI is green.

## Milestone 1: Accounts and login

Sections 4, 6 (first run, passwords and sessions), 13, 15.

- [x] Models and migration: users, sessions, invites, settings
- [x] Setup screen that creates the admin when there are no users
- [x] Login, logout, session cookie, origin check, login throttling
- [x] Current-user dependency and the user-scoping pattern that all later services follow
- [x] `GET /config`; profile settings (name, zone, locale, week start, time format, theme, default view); change password; list and revoke sessions
- [x] Admin area: list users, invite, deactivate and reactivate, delete, reset link, granting and revoking admin rights with the last-admin and self-change guards (section 6), open registration toggle
- [x] Deactivation and admin revocation that take effect at once
- [x] CLI: `reset-password`, `disable-totp`, `make-admin`
- [x] Invite acceptance, self-registration and password reset pages
- [x] Security headers and CSP
- [x] App shell: the responsive layout from section 11 with empty content, settings and admin pages inside it

**Acceptance:** On a fresh instance I can create the admin, invite a second user by link, log in as each on a phone-sized and a desktop-sized window, and revoke a session from the other device. The last active admin cannot be demoted, deactivated or deleted, admins cannot demote or deactivate themselves, and a deactivated user's session stops working at once.

## Milestone 2: Calendars and events on the server

Sections 4, 5 (storing time, occurrences endpoint), 7.

- [x] Models and migration: calendars, events (all columns, including recurrence ones), tags, event_tags
- [x] Default "Personal" calendar for new users; calendar CRUD, ordering, visibility
- [x] Event create, read, update, delete for non-recurring events, timed and all-day, with tags
- [x] `GET /occurrences` with display-zone conversion and range limits
- [x] Tags: created on first use with an automatic colour, list, rename, recolour, delete
- [x] Tests for zones, all-day handling, range boundaries, and cross-user access

**Acceptance:** Through `/api/docs` I can create calendars and events and query a week of occurrences in two different display zones and get correct wall-clock times in each.

## Milestone 3: The calendar UI

Section 11.

- [ ] FullCalendar integrated and restyled; month, week, day and agenda views; phone variants (three-day week, dot month with day list, agenda as default)
- [ ] Navigation: today, previous, next, mini month, swipe on touch, view and date in the URL
- [ ] Sidebar and drawer: calendar list with visibility toggles, calendar create and edit, tag filters with the rename, colour and delete menu
- [ ] Event rendering from section 11: tinted blocks with a colour bar, tag markers in week, day and agenda, the shared colour palette checked in both themes
- [ ] Tag field in the event editor with autocomplete and create-on-type
- [ ] Quick create popover; full event editor (bottom sheet on a phone); event detail popover
- [ ] Drag to move and resize with optimistic update and rollback; long-press drag on touch
- [ ] Undo toast for delete and move
- [ ] Now indicator, scroll to current time, device-zone banner
- [ ] Keyboard and focus handling for dialogs and popovers

**Acceptance:** I can run my week from the UI on a laptop and on a phone: create by clicking and by dragging, edit, move, resize, delete and undo, switch views, hide a calendar, filter by a tag. Nothing overflows or needs horizontal scrolling at 360 px width.

## Milestone 4: Recurring events

Section 5 (expanding, editing a series, the editor).

- [ ] Expansion in `services/recurrence.py` with exdates, overrides and the safety limits
- [ ] The three edit scopes for update and delete
- [ ] Occurrence ids; `scope` and `occurrence` parameters on the event endpoints
- [ ] Recurrence editor: presets, custom rule, readable summary, handling of rules it cannot represent
- [ ] Scope dialog on edit, delete and drag of a series occurrence
- [ ] The full recurrence test list from section 17

**Acceptance:** A weekly meeting stays at the same local time across a daylight saving change. I can move one occurrence, delete another, change "this and following" to a new time, and each change affects exactly the occurrences it should.

## Milestone 5: Search

Section 9.

- [ ] FTS5 table kept in sync with events and tags
- [ ] `GET /search` with prefix matching, diacritic folding and the result ordering from the spec
- [ ] Search field with live results; choosing one navigates and opens the event

**Acceptance:** Typing "zubar" finds an event titled "Zubař". A recurring event appears once, pointing at its next occurrence.

## Milestone 6: ICS

Section 10.

- [ ] Serialiser and parser mapping every field in the spec, including overrides, exdates, tags and alarms
- [ ] Import with UID matching and a result report; export
- [ ] Secret feed URL per calendar: create, regenerate, remove
- [ ] Subscription calendars: add by URL, read-only enforcement, background refresh with conditional requests, error display, manual refresh
- [ ] The background loop in `scheduler.py` (first user is subscription refresh)
- [ ] SSRF protections and their tests
- [ ] Fixture files from Google, Apple and Outlook; round-trip tests

**Acceptance:** I can export a calendar and import it into an empty one and see the same events, including a series with exceptions. A subscribed public holiday calendar appears, is read-only, and refreshes. A feed URL added to another calendar app shows my events.

## Milestone 7: PWA and offline reading

Section 12.

- [ ] Manifest from `branding.json`, icons, service worker in `injectManifest` mode
- [ ] Precached shell; runtime caching for the read endpoints; background prefetch of the surrounding months
- [ ] Offline banner and disabled writes
- [ ] Cache clearing on logout and on user change
- [ ] Update-available prompt
- [ ] iOS add-to-home-screen hint

**Acceptance:** Installed on a phone, the app opens in airplane mode and shows this month's events, with editing visibly unavailable. After logging out, nothing of mine is left in the caches.

## Milestone 8: Reminders

Section 8.

- [ ] Models and migration: reminders, push_subscriptions, notification_log
- [ ] Reminder editing in the event editor, for timed and all-day events; calendar default reminder
- [ ] `next_fire_at_utc` maintenance on every relevant change
- [ ] Reminder tick in the background loop with the late rule, idempotency and retries
- [ ] Web Push: VAPID keys, subscribe and unsubscribe per device in settings, service worker handlers, dead-subscription cleanup
- [ ] E-mail: SMTP sender, templates for reminder, invite and reset; test-mail button in admin; features hidden when SMTP is absent
- [ ] Server-side locale file for notification texts
- [ ] Password reset by e-mail, and e-mailing of invites, now that mail exists
- [ ] Scheduler tests with frozen time

**Acceptance:** An event ten minutes from now with a five-minute reminder produces a push notification on my phone and an e-mail, each exactly once, and tapping the notification opens the event. A weekly series reminds me every week. Restarting the container does not send anything twice.

## Milestone 9: TOTP, OIDC and API tokens

Section 6 (TOTP, OIDC, API tokens).

- [ ] TOTP enrolment with QR code, confirmation, recovery codes; two-step login; disable; admin reset
- [ ] OIDC login with the account resolution order from the spec; link and unlink in settings; `APP_PASSWORD_LOGIN_ENABLED`, including first-run setup through OIDC when password login is off
- [ ] API tokens: create with scope and expiry, show once, list, revoke; Bearer authentication; scope enforcement and the blocked endpoint groups
- [ ] Tests for each flow, with a fake OIDC provider

**Acceptance:** With TOTP on, login asks for a code and a recovery code works once. Login through a real provider (for example a local Keycloak or Authentik) works, and an unknown user is refused unless auto-provisioning is on. A read token can list occurrences with `curl` and is refused when it tries to create an event or touch `/me/tokens`.

## Milestone 10: Release

Sections 16, 17.

- [ ] Nightly cleanup job
- [ ] Startup configuration validation with clear messages
- [ ] Playwright suite from section 17, on desktop and phone viewports, running in CI against the image
- [ ] Release workflow: multi-arch build and push to GHCR on a version tag
- [ ] `README.md`, `CONTRIBUTING.md`, `CHANGELOG.md`
- [ ] Review pass over the whole app: empty states, loading states, error messages, every string through i18n, accessibility with keyboard only, both themes, 360 px width
- [ ] Design pass against section 11 "Visual design": no rounded corners, no raw colour values outside the tokens, no stray shadows, mono used for times and numbers

**Acceptance:** Following only the README on a clean machine, a person can get a running instance behind HTTPS, and tagging `v0.1.0` publishes an image that runs on both a PC and a Raspberry Pi.
