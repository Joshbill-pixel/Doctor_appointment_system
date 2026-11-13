# BSU Medical Centre · Consultation & Appointment Portal

A Django web portal for booking doctor consultations at Benue State University's medical centre. Patients book online, print an appointment letter, and anyone can verify that letter with its appointment ID or token.

## Features

- **Booking:** choose a department, a doctor and a live time slot. Double-booking is blocked in code and by a database constraint.
- **Printable appointment letter (PDF):** shows the appointment ID, a secret verification token, visit details and a QR code.
- **Public verification:** `/verify/` accepts the ID or the token (or a scanned QR code). Patient names are masked. Cancelled letters stop verifying immediately.
- **Patient area:** dashboard, appointments, reschedule and cancel (until a cutoff), feedback after visits, notifications, profile.
- **Doctor portal:** daily schedule, mark visits completed or no-show, private clinical notes.
- **Accounts:** signup with password-strength feedback, sign-in by email with "keep me signed in", password reset.
- **Reminders:** `send_reminders` notifies patients of tomorrow's visits. Safe to run repeatedly.
- **Admin:** search, filters, bulk outcome actions, and doctor schedules.

## Setup

Requires Python 3.10 or newer.

```bash
python3 -m venv .appointment              # Windows: python -m venv .appointment
source .appointment/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo         # optional: demo doctors, patient and appointments
python manage.py createsuperuser   # staff/admin account
python manage.py runserver
```

Open http://127.0.0.1:8000.

Demo accounts created by `seed_demo` (local testing only, never use in production):

- Patient: `patient@bsu.demo` / `Patient@2026`
- Doctors: any `firstname.lastname@bsu.demo` (for example `amina.yusuf@bsu.demo`) / `Doctor@2026`

## Configuration

Set these environment variables for anything beyond local testing:

| Variable | Purpose |
| --- | --- |
| `DJANGO_SECRET_KEY` | Long random secret. Required in production. |
| `DJANGO_DEBUG` | `False` in production (default `True`). |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated host names, e.g. `portal.bsu.edu.ng`. |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Comma-separated origins, e.g. `https://portal.bsu.edu.ng`. |
| `SITE_URL` | Public base URL. **Printed into every letter's QR code.** |
| `DJANGO_EMAIL_BACKEND` | Defaults to console output. Use SMTP in production. |
| `DJANGO_EMAIL_HOST`, `DJANGO_EMAIL_PORT`, `DJANGO_EMAIL_HOST_USER`, `DJANGO_EMAIL_HOST_PASSWORD`, `DJANGO_EMAIL_USE_TLS` | SMTP settings. |
| `DJANGO_DEFAULT_FROM_EMAIL` | Sender address for system emails. |
| `CLINIC_PHONE`, `CLINIC_EMAIL` | Contact details shown on the site and letters. |

Clinic name, address, booking window (`BOOKING_WINDOW_DAYS`) and the cancellation cutoff (`CHANGE_CUTOFF_HOURS`) are in `medical/settings.py`.

## Daily operation

- **Reminders:** run `python manage.py send_reminders` once a day, for example from cron at 16:00:
  `0 16 * * * cd /path/to/project && .venv/bin/python manage.py send_reminders`
- **Doctors and schedules:** create a user in the admin, then add a Doctor profile with its department, slot length and weekly schedule blocks.
- **Recording outcomes:** doctors mark visits completed or no-show in the doctor portal. Admins can do the same in bulk from the appointment list.

## How verification works

Each appointment has two codes printed on its letter:

- **Appointment ID**, for example `BSU-K7Q2X9`. Easy to read and share.
- **Verification token**, for example `TSPL-BRSS-PYMA-PBJ7`. Longer and not guessable. It is encoded in the QR code.

Both codes avoid look-alike characters (no 0, O, 1 or I). The verify page accepts either code, with or without hyphens and spaces.

## Project layout

```
medical/          settings and root URLs
accounts/         patient profile, signup, login, profile, password views
clinic/           departments, doctors, schedules, appointments, notifications
  services.py     all booking, rescheduling, cancellation and notification rules
  letter.py       printable PDF letter generator
  views.py        request handling only
  tests.py        automated tests
templates/        HTML templates (base layout, patient, doctor and account pages)
static/css/       design system
static/js/        progressive enhancement (slot picker, theme, menus)
```

## Troubleshooting

- **Page appears without styling (plain white or default blue links):** open the browser's developer tools, go to the Network tab, reload, and check that `/static/css/app.css` returns status 200. The project serves its own static files in every mode, so a 404 usually means the folder was not unzipped in full or the server was started from a different folder.
- **Database errors on first run:** run `python manage.py migrate` before the server starts.

## Password fields

Every password field has a **Show / Hide** button, so people can check what they typed before submitting. The button is added by the page's JavaScript; the form still works without it.

## Running the tests

```bash
python manage.py test clinic accounts
```

## Before going live

- Set a real `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=False` and the production `ALLOWED_HOSTS`. With `DEBUG` off, secure cookies, HSTS-friendly headers and `X-Frame-Options: DENY` are enabled automatically. Set `DJANGO_BEHIND_HTTPS_PROXY=False` if the site is not behind a proxy that sets `X-Forwarded-Proto`.
- Configure SMTP so reminders and password resets are actually delivered.
- Put the site behind HTTPS, since the QR codes and verify links depend on it.
- Consider encrypting health-related fields at rest, and review your data-retention policy for visit reasons and doctor notes.
- Add login rate limiting at the web server or with a package such as `django-axes`.
