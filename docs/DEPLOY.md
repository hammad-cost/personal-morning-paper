# Putting Vale online (all on Render)

Both halves run on **Render**'s free plan from one blueprint (`render.yaml`):

- **vale-api**: the FastAPI backend (web service)
- **vale-web**: the React website (static site, served from Render's CDN)

Accounts, reader data and story pictures live in **Supabase**, email goes through
**Brevo**, and **cron-job.org** wakes the API for the 7am paper. Keys come from your local
`backend/.env` and `frontend/.env`. Never put the Supabase *secret* key in vale-web.

## 1. Create both services

1. https://render.com → sign in with GitHub → **New → Blueprint** → pick the
   `personal-morning-paper` repo. (Already made vale-api from the blueprint? Open that
   Blueprint and press **Manual Sync**: Render adds vale-web.)
2. Render asks for the values marked *sync: false*:

   **vale-api** (from `backend/.env`): `GEMINI_API_KEY`, `SUPABASE_URL`,
   `SUPABASE_PUBLISHABLE_KEY`, `SUPABASE_SECRET_KEY`, `BREVO_API_KEY`, `MAIL_FROM_EMAIL`.
   For `PUBLIC_APP_URL` and `ALLOWED_ORIGINS` type `http://localhost:5173` for now.

   **vale-web** (from `frontend/.env`): `VITE_SUPABASE_URL`, `VITE_SUPABASE_PUBLISHABLE_KEY`,
   `VITE_COPILOTKIT_PUBLIC_API_KEY`. For `VITE_API_BASE` type `http://localhost:8000` for now.
3. **Apply** and wait until both say *Live* (3–5 minutes). Note the two addresses, e.g.
   `https://vale-api-ab12.onrender.com` and `https://vale-web.onrender.com`.

## 2. Connect them

- **vale-web → Environment**: `VITE_API_BASE` = the vale-api address (no trailing `/`).
  Save, then **Manual Deploy → Deploy latest commit** (the address is baked in at build time).
- **vale-api → Environment**: `PUBLIC_APP_URL` = the vale-web address, `ALLOWED_ORIGINS` =
  the vale-web address. Save (it redeploys by itself). `PUBLIC_API_URL` is not needed: Render
  tells the API its own address.
- **Supabase → Authentication → URL Configuration**: *Site URL* = the vale-web address;
  *Redirect URLs* → add `https://<vale-web address>/**` (keep `http://localhost:5173/**`).
- **Copilot Cloud** (https://cloud.copilotkit.ai): if the Editor chat won't connect on the live
  site, add the vale-web address to your public key's allowed origins.

Check: `<vale-api address>/api/health` shows `{"ok":true}`, and the vale-web address shows
the Vale sign-in page.

## 3. The 7am morning paper (cron-job.org)

Render's free web service sleeps after 15 minutes without visitors, so something wakes it.

1. https://cron-job.org → sign up → **Create cronjob** twice, timezone *Asia/Karachi*:
   - **Wake up**: GET `<vale-api address>/api/health` every day at **06:50**.
   - **Send papers**: `<vale-api address>/api/cron/daily` every day at **07:00**; under
     *Advanced*: method **POST**, header `X-Cron-Secret` = the `CRON_SECRET` value from
     vale-api → Environment.
2. "Timeout" on the send job is fine: the server keeps working after the request ends.
   Each reader gets at most one morning email a day.

## 4. Check it

1. Open the vale-web address on your phone and sign in with your email link.
2. Your paper prints (the first visit after a sleep takes ~50 s while the API wakes up).
3. **You → Send this paper to my email**: PDF attached, links work.
4. Download the PDF and scan a QR code.

## What lives where

| Thing | Where | Survives restarts |
|---|---|---|
| Website | Render static site vale-web | yes |
| Accounts | Supabase Auth | yes |
| Each reader's profile, weights, editions | Supabase table `vale_readers` | yes |
| Story pictures | Supabase Storage bucket `vale-images` (private, served by the API) | yes |
| Publisher logos | vale-api disk (re-fetched after a restart) | cache only |
