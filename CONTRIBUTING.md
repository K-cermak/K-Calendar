# Contributing

Thanks for helping. This file covers how the project is put together and what a change needs before it is merged. The development setup is in the [README](README.md#development).

## Before you start

- [docs/SPEC.md](docs/SPEC.md) is the source of truth for behaviour, the data model and the time zone rules. If a change needs the spec to say something else, change the spec in the same pull request and say why.
- Some decisions were made on purpose and are not up for casual replacement: SQLite rather than another database, one server process with the reminder loop inside it, the server doing all time zone and recurrence work. Open an issue first if you think one of them is wrong.
- Features listed as out of scope in the spec (sharing between users, CalDAV, attendees, tasks, editing offline, …) are not accepted. The aim is a small app.

## How the code is organised

- **The server owns time.** Time zone conversion and the expansion of repeating events happen only in `backend/app/services/zones.py` and `recurrence.py`. The frontend shows the wall-clock strings the API returns and sends wall-clock strings back with the zone they are in; it never expands a rule or converts between zones. FullCalendar runs in UTC mode for that reason, so it does no conversion of its own.
- **Thin routers.** Routers in `backend/app/api` validate and delegate; logic and queries live in `backend/app/services`.
- **Every query is scoped to the current user.** Someone else's resource answers 404, not 403. Each new endpoint gets a test in which a second user tries to reach the first user's data.
- **Generated API types.** The frontend never writes API types by hand. After changing an endpoint or schema, run `just api-types` and commit the result; CI fails when it is out of date.
- **Server state in TanStack Query, interface state in Pinia.** Components read the API through the queries in `frontend/src/api/`.
- **Migrations.** Every schema change is a new Alembic migration. Never edit one that has been committed.
- **Untrusted text.** Event text can come from any calendar on the internet. Never render it as HTML.

## Interface

- Every string a user sees goes through i18n: `frontend/src/locales/en.json` for the interface, `backend/app/locales/en.json` for e-mails and push notifications.
- The app name lives only in `branding.json`. Do not write it anywhere in the code.
- The look follows SPEC section 11, "Visual design": colours only from the tokens and the calendar palette, square corners, hairlines instead of shadows, the monospace face for times and numbers.
- `frontend/src/styles/tokens.css`, `base.css` and `ui.css` are shared with another project and stay plain CSS so the two can be kept in step. Use the `.ui-*` classes before styling an element by hand. Styles only this app needs go in `main.css`, the palette in `palette.css`, FullCalendar's in `fullcalendar.css`.
- Icon buttons need an accessible name, dialogs keep and return the focus, and everything except dragging works from the keyboard.

## Tests

Most of the logic is in the backend, and so are most of the tests. Recurrence and time zones get the deepest coverage: a change there needs tests across daylight saving changes in both directions and in more than one zone. Vitest covers the logic that lives in the frontend (recurrence rule building and summaries, dates, reminders), not each component. Playwright covers the main flows against the built image, on a desktop and a phone viewport.

Before pushing, run:

```sh
just check      # lint, types and unit tests of both sides
just test-e2e   # builds the image and runs Playwright against it
```

Then run the app with `just dev` and try the change yourself, in both themes and at 360 px width if it touches the interface.

## Commits and pull requests

- Small commits, one logical change each.
- [Conventional Commits](https://www.conventionalcommits.org/) messages: `feat:`, `fix:`, `test:`, `docs:`, `chore:`. Say why in the body when the subject cannot.
- Code comments explain why, a workaround or a gotcha, never what the next line plainly does.
- Code, comments, commit messages and documentation are in English.

## Releasing

1. Set the new version in `backend/pyproject.toml` and `frontend/package.json`, and run `cd backend && uv lock` so the lockfile follows.
2. Commit, then tag and push: `git tag v1.2.3 && git push origin main v1.2.3`.

The release workflow runs all checks again, refuses a tag that does not match the version in `backend/pyproject.toml`, and publishes `ghcr.io/k-cermak/k-calendar` for `linux/amd64` and `linux/arm64`, tagged with the version and, for a release that is not a pre-release, `latest`. The GitHub release and its notes are written by hand. Every release uses this form:

Title: `K-Calendar {version}`

Description:

````markdown
Contains K-Calendar {version}.

https://k-calendar.karlosoft.com/

## Changelog (differences compared to {previous_version}):
- Updated

**Full Changelog**: https://github.com/K-cermak/K-Calendar/compare/v{previous_version}...v{version}
````

`{version}` and `{previous_version}` are bare version numbers such as `1.1.0` and `1.0.0`; the compare link adds the `v` of the tag. The changelog lists the changes as bullets.
