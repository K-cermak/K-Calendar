# Calendar

A simple, self-hosted personal calendar. Web app, installable on phones as a PWA, shipped as one Docker image, released as open source under MIT. Several people can have accounts on one instance, but nobody shares anything with anybody: every calendar belongs to exactly one user.

"Calendar" is a working name. It lives only in `branding.json`; never hard-code it anywhere else.

## Read these first

- `docs/SPEC.md` is what we are building and why each decision was made. It is the source of truth.
- `docs/PLAN.md` is the order to build it in, as milestones with checkboxes.
- `docs/design/reference.css` is a stylesheet from another of the owner's products. It shows the visual style to match. Read it before any UI work; do not import it.

## How to work

1. Open `docs/PLAN.md` and take the first milestone that has unchecked items. Work on one milestone at a time, in order. Later milestones depend on earlier ones.
2. Read the SPEC sections that milestone points to before you write code.
3. Build it, with tests written alongside the code, not after.
4. Run the full check suite (below). A milestone is done only when everything passes and its acceptance criteria hold when you actually exercise the app.
5. Tick the checkboxes in `docs/PLAN.md` and commit.
6. Stop and report: what was built, what was verified and how, anything that deviates from the SPEC, and open questions. Do not start the next milestone until the owner confirms.

The decisions in the SPEC were made with the project owner. Do not swap out the stack or re-open them. If the SPEC is silent, wrong, contradicts itself, or cannot work, stop, say so and propose a change to the SPEC before coding around it, however small the deviation.

Anything listed under "Out of scope" in the SPEC stays out, even when it looks easy to add. The owner wants a small app.

## Stack

- Backend: Python, FastAPI, SQLAlchemy 2 (sync), Alembic, SQLite, managed with `uv`
- Frontend: Vue 3 with TypeScript, Vite, Pinia, Vue Router, TanStack Query, vue-i18n, Tailwind CSS, Reka UI, FullCalendar, managed with `pnpm`
- One Docker image: FastAPI serves the API and the built frontend
- Commands run through `just`

Use the latest stable version of every dependency at the time you add it, and pin it through the lockfiles (`uv.lock`, `pnpm-lock.yaml`).

## Commands

Milestone 0 creates these. Keep this section accurate when they change.

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
just icons            # render the PWA icons in frontend/public from icon.svg
just screenshots      # render the README screenshots in docs/screenshots from the built image
```

Toolchain: Python 3.15 (`backend/.python-version`), Node 26 (`.node-version`), pnpm 12. TypeScript stays on 6.0 until vue-tsc and typescript-eslint support 7. Playwright needs `pnpm exec playwright install chromium` once.

The shared design files `frontend/src/styles/tokens.css`, `base.css` and `ui.css` come from the owner's K-Notes project and stay plain CSS so they can be kept in step with it. Use the `.ui-*` classes before styling an element by hand. Calendar-only styles go in `main.css` and `palette.css`.

## Conventions

- Every database query for user data is scoped to the current user. A resource that belongs to someone else returns 404, not 403. Every new endpoint gets a test where user B tries to reach user A's data.
- The server does all time zone and recurrence math. The frontend never expands a recurrence rule and never converts between zones. See SPEC section 5.
- The frontend never hand-writes API types. They come from `just api-types`.
- Backend: `ruff` for lint and format, `pyright` for types. Frontend: `eslint`, `prettier`, `vue-tsc`.
- The look is specified in SPEC section 11 "Visual design" and shown in `docs/design/reference.css`. Colours come from the design tokens only, corners are square, and surfaces are separated by hairlines rather than shadows.
- Every string a user can see goes through i18n: `frontend/src/locales/en.json` for the UI, `backend/app/locales/en.json` for e-mails and push notifications.
- Backend layering: routers in `app/api` stay thin, logic lives in `app/services`, routers do not query the database directly.
- Migrations: every schema change is an Alembic migration. Never edit a migration that has been committed.
- Comments explain why, never what. No comments that restate the code.
- Commits: small, one logical change each, Conventional Commits format (`feat:`, `fix:`, `test:`, `docs:`, `chore:`). Commit to the active branch.
- Everything in the repository is written in English: code, comments, docs, commit messages.
