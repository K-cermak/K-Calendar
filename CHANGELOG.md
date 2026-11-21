# Changelog

Notable changes to this project. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and versions follow [Semantic Versioning](https://semver.org/).

## [0.1.0] - Unreleased

The first release.

### Added

- Month, week, day and agenda views, with a three-day week and an agenda on phones; drag to move and resize, drag over empty time to create, Undo after a move or a delete.
- Several calendars per person with colours and visibility, coloured tags, events with a time zone, all-day events, location, description and an own colour.
- Repeating events with exceptions, changed as "this event", "this and following events" or "all events", expanded by the server in the event's local time so they keep their hour across daylight saving changes.
- Search that ignores case and accents.
- Reminders by Web Push and by e-mail, delivered once per occurrence and channel even across restarts, with retries.
- Import and export of `.ics` files, a secret feed address per calendar, and read-only subscriptions to calendars on the internet with protection against requests into private networks.
- Installable app that keeps loaded calendars readable offline, with an update prompt.
- Accounts: first-run setup, invite links, optional open registration, password reset links by e-mail, two-step verification with recovery codes, single sign-on through OIDC, sessions that can be revoked.
- Administration: users, admin rights, deactivation, deletion, instance settings and status, a test e-mail.
- Personal API tokens with read or read and write scope.
- Light and dark theme.
- A multi-architecture Docker image (`linux/amd64`, `linux/arm64`) that serves the app and the API, with checks of the configuration at startup and a nightly clean-up of expired data.
