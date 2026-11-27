# K-Calendar

A simple, self-hosted personal calendar. Web app, installable on phones as a PWA, shipped as one Docker image, released as open source under MIT. Several people can have accounts on one instance, but nobody shares anything with anybody: every calendar belongs to exactly one user.

"K-Calendar" is a working name. It lives only in `branding.json`; never hard-code it anywhere else.

Read `docs/SPEC.md` before writing code. It is what we are building and why each decision was made, and the source of truth for behaviour, the data model and the time zone rules.

The decisions in the SPEC were made with the project owner. Do not swap out the stack or re-open them. If the SPEC is silent, wrong, contradicts itself, or cannot work, stop, say so and propose a change to the SPEC before coding around it, however small the deviation.

Anything listed under "Out of scope" in the SPEC stays out, even when it looks easy to add. The owner wants a small app.

## Stack

- Backend: Python, FastAPI, SQLAlchemy 2 (sync), Alembic, SQLite, managed with `uv`
- Frontend: Vue 3 with TypeScript, Vite, Pinia, Vue Router, TanStack Query, vue-i18n, Tailwind CSS, Reka UI, FullCalendar, managed with `pnpm`
- One Docker image: FastAPI serves the API and the built frontend
- Commands run through `just`

Use the latest stable version of every dependency at the time you add it, and pin it through the lockfiles (`uv.lock`, `pnpm-lock.yaml`).

## Repository layout

```
branding.json        app name, short name, description, theme colour
Dockerfile
docker-compose.yml   example deployment
justfile
backend/
  alembic/
  app/
    main.py          FastAPI app factory, lifespan, static file serving
    config.py        settings from APP_* environment variables
    scheduler.py     the background loop: reminders, subscriptions, nightly cleanup
    api/             routers, one module per resource
    services/        business logic; auth/ and notify/ are subpackages
    cli.py           admin commands (reset-password, disable-totp, make-admin, disable-captcha)
    locales/en.json  texts for e-mails and push notifications
  tests/
frontend/
  src/
    api/             generated schema, typed client, query hooks
    captcha/         script of captcha.html and its messages to the form
    components/
    views/
    stores/          Pinia, UI state only
    locales/en.json
    styles/          tokens.css, base.css, ui.css (plain, shared with K-Notes); main.css, palette.css, fullcalendar.css
    sw.ts            service worker
  captcha.html       the page the captcha widget runs in, framed by the sign-in forms
  e2e/               Playwright tests
docs/                SPEC.md
Images/              logo artwork, README and website screenshots, published on the CDN; ignored by git
private/             the owner's local notes; ignored by git, never commit or publish it
```

## Conventions

- Every database query for user data is scoped to the current user. A resource that belongs to someone else returns 404, not 403. Every new endpoint gets a test where user B tries to reach user A's data.
- The server does all time zone and recurrence math. The frontend never expands a recurrence rule and never converts between zones. See SPEC section 5.
- The frontend never hand-writes API types. They come from `just api-types`.
- Backend: `ruff` for lint and format, `pyright` for types. Frontend: `eslint`, `prettier`, `vue-tsc`.
- The look is specified in SPEC section 11 "Visual design" and built into `tokens.css` and `ui.css`. Colours come from the design tokens only, corners are square, and surfaces are separated by hairlines rather than shadows.
- The shared design files `frontend/src/styles/tokens.css`, `base.css` and `ui.css` come from the owner's K-Notes project and stay plain CSS so they can be kept in step with it. Use the `.ui-*` classes before styling an element by hand. Calendar-only styles go in `main.css` and `palette.css`.
- Every string a user can see goes through i18n: `frontend/src/locales/en.json` for the UI, `backend/app/locales/en.json` for e-mails and push notifications.
- Backend layering: routers in `app/api` stay thin, logic lives in `app/services`, routers do not query the database directly.
- Migrations: every schema change is an Alembic migration, and a released migration is never edited. Until the first release the app is deployed nowhere, so the existing migrations are changed in place instead of adding new ones.
- Comments explain why, never what. No comments that restate the code.
- Commits: small, one logical change each, Conventional Commits format (`feat:`, `fix:`, `test:`, `docs:`, `chore:`). Commit to the active branch, including `main`, unless told otherwise.
- Everything in the repository is written in English: code, comments, docs, commit messages.

## Commands

Keep this section accurate when the commands change.

```
just setup            # install backend (uv) and frontend (pnpm) dependencies
just dev              # backend with reload + Vite dev server (proxies /api); data in backend/.data
just check            # everything CI runs: lint, types, unit tests for both sides
just fmt              # format and autofix both sides
just test-e2e         # build the image, then run Playwright against it
just e2e              # Playwright against an already built image (used by CI)
just api-types        # regenerate frontend/src/api/schema.d.ts from the OpenAPI schema
just api-types-check  # fail if the generated API types are out of date (runs in CI)
just docker           # build the production image locally
just icons            # render the PWA icons in frontend/public and the e-mail logo from icon.svg
just screenshots      # render the README and website screenshots into Images/ from the built image
```

Toolchain: Python 3.15 (`backend/.python-version`), Node 26 (`.node-version`), pnpm 12. TypeScript stays on 6.0 until vue-tsc and typescript-eslint support 7. Playwright needs `pnpm exec playwright install chromium` once.

## Releases

The release steps are in `CONTRIBUTING.md` under "Releasing". GitHub releases are written by hand and always take this form:

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

## Testing

Most of the logic is in the backend, and so are most of the tests. Recurrence and time zones get the deepest coverage: a change there needs tests across daylight saving changes in both directions and in more than one zone. Vitest covers the logic that lives in the frontend, Playwright the main flows against the built image, on a desktop and a phone viewport. A change is not done until `just check` passes and you have run the app and exercised the feature yourself.
