<p align="center">
  <picture>
      <source media="(prefers-color-scheme: dark)" srcset="https://cdn.karlosoft.com/cdn-data/ks/img/kcalendar/logo-dark.svg">
      <source media="(prefers-color-scheme: light)" srcset="https://cdn.karlosoft.com/cdn-data/ks/img/kcalendar/logo-light.svg">
      <img alt="K-Calendar" src="https://cdn.karlosoft.com/cdn-data/ks/img/kcalendar/logo-light.svg" width="500">
  </picture>
  <p align="center">
    <a href="https://k-calendar.karlosoft.com/"><strong>Website</strong></a>
    &nbsp;·&nbsp;
    <a href="#quick-start"><strong>Quick start</strong></a>
    &nbsp;·&nbsp;
    <a href="https://github.com/K-cermak/K-Calendar/issues"><strong>Report a problem</strong></a>
  </p>
</p>

<br>

A small, self-hosted personal calendar: month, week, day and agenda views, repeating events, reminders by push notification and e-mail, and import and export as iCalendar files. It runs in any browser and installs on phones as a web app (PWA). A few people can have accounts on one instance, but nothing is shared between them: every calendar belongs to one person. One container keeps everything in one directory, so a backup is a copy of that directory.

> **Note:** K-Calendar is heavily vibe-coded: most of its code was written with an AI assistant and only partly reviewed by a human. It is fine for everyday plans, but it is not recommended for critical systems or anywhere lost or wrong data could cause harm. Keep backups.

![The week view in the light theme](https://cdn.karlosoft.com/cdn-data/ks/img/kcalendar/github-week-light.png)

| Dark theme | An event's details | On a phone |
| --- | --- | --- |
| ![The week view in the dark theme](https://cdn.karlosoft.com/cdn-data/ks/img/kcalendar/github-week-dark.png) | ![The details of an event over the week view](https://cdn.karlosoft.com/cdn-data/ks/img/kcalendar/github-event.png) | ![The agenda on a phone](https://cdn.karlosoft.com/cdn-data/ks/img/kcalendar/github-phone.png) |

## Features

- Several calendars per person, each with its own colour and each easy to hide; coloured tags across calendars.
- Events with a time zone, all-day events over several days, location, description and an own colour.
- Repeating events, from "every weekday" to "the last Friday of every month", changed as "this event", "this and following events" or "all events".
- Drag to move and resize, drag over empty time to create, search that ignores case and accents.
- Working hours for each day, with breaks, lightly shaded in the week and day views.
- Reminders by Web Push and by e-mail, delivered once even across restarts.
- Import an `.ics` file, export a calendar, a secret feed address per calendar for other apps, and read-only subscriptions to calendars on the internet, such as public holidays.
- Installable app; what was loaded stays readable offline.
- Accounts: first-run setup, invite links, optional open registration, password reset, two-step verification (TOTP) with recovery codes, optional single sign-on through OIDC, an optional captcha on sign-in and registration, and deleting one's own account.
- Personal API tokens with read or read and write access.
- Light and dark theme.

Not included on purpose: sharing calendars or events with other people, CalDAV and two-way sync with Google or Microsoft, attendees and invitations, tasks, creating or changing events while offline, a year view.

## Quick start

You need Docker with Compose, a domain name pointing at the machine, and a reverse proxy that provides HTTPS (see [HTTPS and the reverse proxy](#https-and-the-reverse-proxy)). Browsers allow installing the app and push notifications only over HTTPS.

1. Get the example Compose file and create the data directory. The container runs as user 1000, so that user has to own it:

   ```sh
   mkdir k-calendar && cd k-calendar
   curl -fsSLO https://raw.githubusercontent.com/K-cermak/K-Calendar/main/docker-compose.yml
   mkdir data && sudo chown 1000:1000 data
   ```

2. In `docker-compose.yml`, set `APP_BASE_URL` to the address people will use, such as `https://calendar.example.com`. It must match exactly: the server uses it for links and to refuse requests from other sites. Fill in the SMTP lines if you want reminders and links by e-mail.
3. Start it:

   ```sh
   docker compose up -d
   docker compose logs -f   # optional: watch it start
   ```

4. Set up HTTPS as below, open the address in a browser and create the first account, which becomes the administrator.

To add people, open **Administration** from the account menu and create an invite link. With SMTP set up, the link can go out by e-mail; otherwise pass it on yourself.

On a phone, open the address and use **Add to Home Screen** (Safari: Share → Add to Home Screen; Chrome: the install prompt or the menu). On iPhones, push notifications work only for the app on the home screen.

### Updating

```sh
docker compose pull && docker compose up -d
```

Database migrations run by themselves when the new version starts. Open apps offer to reload into the new version.

## Configuration

All settings are environment variables. Only `APP_BASE_URL` is required. The server checks them at startup and stops with a message that names the variable if one is wrong.

| Variable | Default | Meaning |
| --- | --- | --- |
| `APP_BASE_URL` | (required) | Public address, such as `https://calendar.example.com`, with no path |
| `APP_DATA_DIR` | `/data` | Where the database and the generated secret key live |
| `APP_SECRET_KEY` | generated | At least 32 characters. If unset, one is generated on first start and kept in `APP_DATA_DIR/secret.key`. Changing it makes two-step verification secrets unreadable |
| `APP_TRUSTED_PROXIES` | | Comma-separated addresses or networks of reverse proxies whose `X-Forwarded-*` headers are believed |
| `APP_SMTP_HOST`, `APP_SMTP_PORT` | | Mail server. E-mail is on when the host and `APP_SMTP_FROM` are set |
| `APP_SMTP_USER`, `APP_SMTP_PASSWORD` | | Sign-in at the mail server, if it needs one |
| `APP_SMTP_FROM` | | Sender address |
| `APP_SMTP_SECURITY` | `starttls` | `starttls`, `ssl` or `none` |
| `APP_OIDC_DISCOVERY_URL` | | The provider's `.well-known/openid-configuration` URL |
| `APP_OIDC_CLIENT_ID`, `APP_OIDC_CLIENT_SECRET` | | Single sign-on is on when all three OIDC variables are set |
| `APP_OIDC_PROVIDER_NAME` | `SSO` | Label of the sign-in button |
| `APP_OIDC_AUTO_PROVISION` | `false` | Create accounts for people the provider knows but the app does not |
| `APP_PASSWORD_LOGIN_ENABLED` | `true` | `false` allows sign-in only through OIDC, which must then be configured |
| `APP_VAPID_PUBLIC_KEY`, `APP_VAPID_PRIVATE_KEY` | generated | Keys for push notifications, generated on first start and kept in the database. Set both only to bring keys from elsewhere; changing them stops push on every device until it is turned on again |
| `APP_VAPID_CONTACT` | from `APP_SMTP_FROM` or `APP_BASE_URL` | Contact address sent to push services, as `mailto:` or `https:` |
| `APP_ALLOW_PRIVATE_SUBSCRIPTION_URLS` | `false` | Allow subscribing to calendars on private networks, such as another server at home |
| `APP_LOG_LEVEL` | `info` | `debug`, `info`, `warning`, `error` or `critical` |

How long people stay signed in without using the app is not an environment variable: an administrator sets it under Administration → Limits (180 days until changed).

### Single sign-on (OIDC)

Register the app with your provider (Authentik, Keycloak, Authelia, Google, …) as a confidential client using the authorization code flow, with the redirect URI `https://calendar.example.com/api/v1/auth/oidc/callback` (your `APP_BASE_URL` followed by `/api/v1/auth/oidc/callback`) and the scopes `openid email profile`. Then set the three OIDC variables.

Someone signing in through the provider is matched to an account in this order: an account already linked to them; an account with the same e-mail address, if the provider says the address is verified; a new account, if `APP_OIDC_AUTO_PROVISION` is on. Otherwise they are told to ask an administrator. Signed-in users can link and unlink the provider under Settings → Security.

### Captcha

An administrator can ask for a captcha under Administration → Captcha, on sign-in, on registration (open registration and invite links) or on both. Single sign-on, two-step verification codes and password reset never ask for one.

| Provider | Keys | Privacy |
| --- | --- | --- |
| ALTCHA | none | The browser solves a short calculation (about a second) that this server issues and checks. Nothing goes to a third party, and it works without internet access. |
| Cloudflare Turnstile | site key and secret key from the Cloudflare dashboard | Cloudflare sees the address and browser of everyone who opens the form. |
| Google reCAPTCHA v2 | a v2 "I'm not a robot" checkbox key pair from the reCAPTCHA admin console | Google sees the address and browser of everyone who opens the form. |
| hCaptcha | site key and secret key from the hCaptcha dashboard | hCaptcha sees the address and browser of everyone who opens the form. |

Register your domain with the provider. New keys take effect only after you solve the captcha once on the administration page, so a mistyped key cannot lock anyone out. If keys stop working later, for example because they were deleted at the provider, turn the captcha off from the command line with `disable-captcha` (see below). With a hosted provider, the server must be able to reach its verification endpoint; if it cannot, sign-in is refused rather than let through.

The widget runs in a small page of its own, `/captcha.html`, embedded in the form. Only that page's Content-Security-Policy allows the provider's scripts; the rest of the app keeps its strict policy.

## HTTPS and the reverse proxy

The container speaks plain HTTP on port 8000. Put a reverse proxy in front of it that handles HTTPS. Request bodies up to 10 MB must get through, the largest `.ics` file the app imports.

Run exactly one container: reminders are sent by a loop inside the server process, and SQLite has a single writer, so a second copy would send every reminder twice.

### Caddy

[Caddy](https://caddyserver.com/) gets a certificate by itself:

```caddy
calendar.example.com {
	reverse_proxy 127.0.0.1:8000
}
```

### nginx

```nginx
server {
    listen 443 ssl;
    http2 on;
    server_name calendar.example.com;

    ssl_certificate     /etc/letsencrypt/live/calendar.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/calendar.example.com/privkey.pem;

    # Above the largest .ics file the app imports (10 MB).
    client_max_body_size 12m;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

The example Compose file publishes the port on `127.0.0.1` only, so the calendar is reachable from outside only through the proxy. If the proxy runs in Docker too, point it at the container by its service name (`calendar:8000`) and remove the `ports` section. Either way, `APP_TRUSTED_PROXIES` must cover the address the proxy connects from, so that sign-in throttling and the session list see people's real addresses.

## Backup and restore

Everything lives in the data directory: the SQLite database and the generated secret key.

```sh
docker compose stop
cp -a data "backup-$(date +%F)"
docker compose start
```

Stop the container first, so the database is not copied halfway through a write. To restore, stop the container, replace `data` with the backup and start it again.

Once a night the server deletes expired sign-ins, used or expired invite links and the delivery log of reminders older than a month. It makes no backups itself.

## Administration from the command line

For a locked-out administrator, or when no one else can help. The commands run inside the container, where the `APP_*` variables are already set, and change the database directly; the running app picks the change up at once.

```sh
docker compose exec calendar python -m app.cli <command> [e-mail]
```

With plain Docker, use `docker exec <container> python -m app.cli …` instead.

| Command | What it does |
| --- | --- |
| `reset-password <e-mail>` | Prints a password reset link, valid for 24 hours and usable once, for you to pass on. An older reset link for the same account stops working. A deactivated account cannot use it until it is reactivated. |
| `disable-totp <e-mail>` | Turns off two-step verification and deletes the recovery codes, for someone who lost both their phone and their codes. They can set it up again in their security settings. |
| `make-admin <e-mail>` | Grants admin rights. A deactivated account stays deactivated; reactivate it in the administration. |
| `disable-captcha` | Turns off the captcha on sign-in and registration, for example when its keys were deleted at the provider and nobody can sign in. |

The e-mail address is matched without regard to case. `python -m app.cli --help` lists the commands. The exit code is 0 on success, 1 when the command fails (no account with that address, for example) and 2 for a configuration problem or a mistyped command.

In a development setup, run the same commands from `backend` with `uv run`, pointing them at the development data:

```sh
cd backend
APP_BASE_URL=http://localhost:5173 APP_DATA_DIR=.data uv run python -m app.cli make-admin someone@example.com
```

## REST API

Create a token under Settings → API tokens, with read or read and write access. A token works for calendars, events and tags, never for account, security or admin settings.

```sh
curl -H "Authorization: Bearer $TOKEN" \
     "https://calendar.example.com/api/v1/occurrences?start=2027-02-01&end=2027-02-08"
curl -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
     -d '{"calendar_id": 1, "title": "Dentist", "start": "2027-02-03T08:00:00", "end": "2027-02-03T08:45:00"}' \
     https://calendar.example.com/api/v1/events
```

Times without an offset are wall-clock times in the event's zone, which defaults to the zone in your profile. The full reference is at `/api/v1/docs` on your instance.

## Adding a translation

1. Copy `frontend/src/locales/en.json` to `frontend/src/locales/<code>.json`, for example `de.json`, and translate the values. Keep the keys.
2. Add the language to `LOCALES` in `frontend/src/i18n.ts`, under the same code, with its name in that language: `{ en: 'English', de: 'Deutsch' }`.
3. For e-mails and push notifications, copy `backend/app/locales/en.json` to `backend/app/locales/<code>.json` and translate it too. Keys that are missing fall back to English.

People can then pick the language under Settings → Profile.

## Development

You need Python 3.15 with [uv](https://docs.astral.sh/uv/), Node 26 with pnpm 12, [just](https://just.systems/) and Docker.

```sh
just setup                                                      # install dependencies of both sides
cd frontend && pnpm exec playwright install chromium && cd ..   # once, for end-to-end tests
just dev                                                        # backend on :8000 and Vite on http://localhost:5173
```

Open http://localhost:5173 exactly: `127.0.0.1` is a different address to the browser, and the server refuses changes from it. `just dev` keeps its data in `backend/.data`. Other recipes:

| Command | |
| --- | --- |
| `just check` | Lint, type checks and unit tests of both sides, as CI runs them |
| `just fmt` | Format both sides |
| `just test-e2e` | Build the image and run the Playwright tests against it, on a desktop and a phone viewport |
| `just api-types` | Regenerate the frontend's API types after changing the API |
| `just docker` | Build the image |
| `just screenshots` | Render the README and website screenshots into `Images/` from the built image |
| `just icons` | Render the app icons from `frontend/public/icon.svg` |

The app's name lives only in `branding.json`. How it is built and why is described in [docs/SPEC.md](docs/SPEC.md). See [CONTRIBUTING.md](CONTRIBUTING.md) before sending changes.

## License

MIT, see [LICENSE.md](LICENSE.md).
