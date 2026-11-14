# Deploying the BSU Medical Portal on Render

This guide deploys the portal to [Render](https://render.com) with a **web service** (Django, run by gunicorn) and a **managed PostgreSQL database**. The included `render.yaml` describes both, so most of the setup is one click.

Estimated time: 15 to 20 minutes.

---

## What is in the repository for Render

| File | Purpose |
| --- | --- |
| `render.yaml` | Blueprint: creates the database and web service, sets environment variables. |
| `build.sh` | Build step: installs requirements and collects static files. |
| `requirements.txt` | Python packages, including `gunicorn`, `whitenoise`, `dj-database-url` and `psycopg`. |
| `.python-version` | Python 3.11 for local tools. Render uses `PYTHON_VERSION` from `render.yaml`. |
| `medical/settings.py` | Reads all deployment values from environment variables. |

On each start, the service runs `python manage.py migrate` and then gunicorn. Migrations are safe to repeat.

---

## Step 1: Put the project on GitHub

Render deploys from a Git repository. Make sure the repository does not include the bundled macOS virtual environment (`.appointment/`) or your local database.

From the project folder:

```bash
# The .appointment folder was committed by mistake. Stop tracking it (files stay on disk).
git rm -r --cached .appointment
git rm --cached db.sqlite3 2>/dev/null || true

git add .
git commit -m "Prepare for Render deployment"
```

Create an empty repository on GitHub (for example `bsu-medical-portal`), then push:

```bash
git branch -M main
git remote add origin https://github.com/<your-username>/bsu-medical-portal.git
git push -u origin main
```

Keep the repository private if it will contain real patient-related code or configuration.

---

## Step 2: Create the services from the Blueprint

1. Sign in at [dashboard.render.com](https://dashboard.render.com) and connect your GitHub account when asked. Allow access to the repository you just created.
2. Click **New +** → **Blueprint**.
3. Choose the `bsu-medical-portal` repository and the `main` branch.
4. Render shows the two resources from `render.yaml`:
   - `bsu-medical-db` (PostgreSQL)
   - `bsu-medical-portal` (web service)
5. Click **Apply** (or **Deploy Blueprint**).

Render now creates the database, generates a random `DJANGO_SECRET_KEY`, connects the web service to the database through `DATABASE_URL`, and starts the first build. The first build takes a few minutes. Watch progress under **Events** and **Logs** on the web service.

When the log shows `Booting worker` and the service status is **Live**, the site is running.

> If you prefer to create the services by hand instead of using the Blueprint, see *Manual setup* at the end of this guide.

---

## Step 3: Check the site

Your site address looks like `https://bsu-medical-portal.onrender.com` (the name may differ). The URL is shown at the top of the service page.

Check these pages:

- `https://<your-app>.onrender.com/` shows the home page with its styling.
- `https://<your-app>.onrender.com/doctors/` lists departments and doctors (empty until you add doctors).
- `https://<your-app>.onrender.com/admin/` shows the admin login. You need a staff account, which you create in Step 4.

The site is empty on purpose. Production does not include demo data.

---

## Step 4: Create the administrator account

Use **Shell** on the web service: open the service in the Render dashboard and choose **Shell**, then run:

```bash
python manage.py createsuperuser
```

Enter a username, an email address and a strong password. Sign in at `/admin/`.

Then, in the admin:

1. Create **Department** records if they were not created by the migrations. A starter set is included.
2. Create **doctor** user accounts, then add a **Doctor** profile for each one with its department, slot length and weekly schedule.
3. Doctors can then sign in and manage their own appointments.

> Do not run `python manage.py seed_demo` in production. It creates demo accounts with known passwords.

---

## Step 5: Configure email (recommended before go-live)

Without SMTP, reminder emails and password-reset emails are only printed to the Render logs, so patients will not receive them.

In the web service, open **Environment** and add:

| Key | Example value |
| --- | --- |
| `DJANGO_EMAIL_BACKEND` | `django.core.mail.backends.smtp.EmailBackend` |
| `DJANGO_EMAIL_HOST` | `smtp.your-provider.com` |
| `DJANGO_EMAIL_PORT` | `587` |
| `DJANGO_EMAIL_HOST_USER` | your SMTP username |
| `DJANGO_EMAIL_HOST_PASSWORD` | your SMTP password (add it as a secret value) |
| `DJANGO_EMAIL_USE_TLS` | `True` |
| `DJANGO_DEFAULT_FROM_EMAIL` | `BSU Medical Centre <no-reply@your-domain>` |

Save the changes. Render restarts the service automatically.

Also update `CLINIC_PHONE` and `CLINIC_EMAIL` with the real contact details. They appear on the site and on printed letters.

---

## Step 6: Reminders (daily)

The appointment reminder command should run once a day. On Render, create a **Cron Job**:

1. **New +** → **Cron Job**, and select the same repository.
2. **Build command:** `bash build.sh`
3. **Command:** `python manage.py send_reminders`
4. **Schedule:** `0 15 * * *` (15:00 UTC, which is 16:00 in Lagos).
5. **Environment:** copy every variable from the web service, or link them as a shared environment group. The job needs `DATABASE_URL`, `DJANGO_SECRET_KEY` and the email settings.

The command is safe to run repeatedly.

---

## Step 7: Custom domain (optional)

To use a domain such as `portal.bsu.edu.ng`:

1. In the web service, open **Settings** → **Custom Domains** → **Add Custom Domain**, and enter the domain.
2. Create the DNS record that Render shows at your domain registrar.
3. Add the domain to the environment (**Environment** tab):

   | Key | Value |
   | --- | --- |
   | `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1,portal.bsu.edu.ng` |
   | `DJANGO_CSRF_TRUSTED_ORIGINS` | `https://portal.bsu.edu.ng` |
   | `SITE_URL` | `https://portal.bsu.edu.ng` |

   `SITE_URL` must match the public address, because it is printed into every appointment letter's QR code.

Render issues the HTTPS certificate automatically.

---

## Updating the site

Push to the `main` branch on GitHub. Render builds and deploys automatically (auto-deploy is on by default). Migrations run on startup.

```bash
git add .
git commit -m "Describe your change"
git push
```

---

## Environment variables reference

| Variable | Set by | Notes |
| --- | --- | --- |
| `DATABASE_URL` | Blueprint (from database) | Do not edit by hand. |
| `DJANGO_SECRET_KEY` | Blueprint (generated) | Required. Keep it secret. Changing it logs out all users. |
| `DJANGO_DEBUG` | Blueprint | `False`. Never set to `True` on the live site. |
| `RENDER_EXTERNAL_HOSTNAME` | Render (automatic) | The `.onrender.com` host. Allowed and trusted automatically. |
| `DJANGO_ALLOWED_HOSTS` | You | Add custom domains here. |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | You | Add custom domains here as `https://...`. |
| `SITE_URL` | Optional | Defaults to the `.onrender.com` address. |
| `CLINIC_PHONE`, `CLINIC_EMAIL` | Blueprint | Replace the placeholders. |
| `DJANGO_EMAIL_*` | You | See Step 5. |
| `DJANGO_SSL_REDIRECT` | Optional | Default `False`. Render already redirects HTTP to HTTPS. |
| `DJANGO_HSTS_SECONDS` | Optional | Default `3600`. |
| `DJANGO_LOG_LEVEL` | Optional | Default `INFO`. |

---

## Free plan limits

The free plan is fine for testing and demonstrations. For a live clinic, plan for the following:

- **The web service sleeps after about 15 minutes without traffic.** The next visitor waits roughly a minute while it wakes up. Upgrade to a paid instance type to avoid this.
- **Free PostgreSQL databases expire after 30 days.** Render warns you beforehand. Upgrade to a paid database plan and enable backups before storing real appointments.
- **The web service's disk is temporary.** The portal stores everything in PostgreSQL, so this does not affect data. Do not store uploads on the instance disk.

---

## Troubleshooting

**Build fails on `pip install`.** Open the build log and read the first error. The usual cause is a package that needs a compiler. The versions in `requirements.txt` all have prebuilt Linux wheels for Python 3.11.

**`ImproperlyConfigured: DJANGO_SECRET_KEY must be set`.** The environment variable is missing. Add it in **Environment**, or redeploy the Blueprint to generate it.

**`DisallowedHost at /`.** The address you are using is not in `ALLOWED_HOSTS`. Add the custom domain as described in Step 7.

**CSRF verification failed on login or forms.** The site is being accessed through an origin that is not trusted. Add the address to `DJANGO_CSRF_TRUSTED_ORIGINS` with `https://`.

**Pages load without styling.** Check that the build log shows `collectstatic` and "static files copied". Redeploy the service with **Manual Deploy** → **Clear build cache & deploy** if it does not.

**`relation does not exist` or other migration errors.** Open **Shell** and run `python manage.py migrate` to see the full error. Check that `DATABASE_URL` is set.

**The appointment letter QR code points to the wrong address.** Set `SITE_URL` to the public address (see Step 7).

**Logs.** Open the web service and choose **Logs**. Errors appear there, with full tracebacks.

---

## Manual setup (without the Blueprint)

1. **New +** → **PostgreSQL**. Choose a name, a region and a plan, then create it. Copy its **Internal Database URL**.
2. **New +** → **Web Service**. Connect the repository.
   - **Runtime:** Python 3
   - **Build command:** `bash build.sh`
   - **Start command:** `python manage.py migrate --no-input && gunicorn medical.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120 --access-logfile -`
   - **Health check path:** `/`
3. Add these environment variables:
   - `PYTHON_VERSION` = `3.11.9`
   - `DJANGO_DEBUG` = `False`
   - `DJANGO_SECRET_KEY` = a long random string (generate one with `python -c "import secrets; print(secrets.token_urlsafe(50))"`)
   - `DATABASE_URL` = the Internal Database URL from step 1
   - Any others from the reference table above
4. Deploy.
