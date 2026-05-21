# Railway setup

1. Create a new Railway project from the GitHub repository.
2. Railway will use the included Dockerfile and start command:
   `uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}`.
3. Add environment variables in Railway, not in GitHub:
   - `LICENSE_KEY`
   - `ANTHROPIC_API_KEY`
   - `GOOGLE_CLIENT_ID`
   - `GOOGLE_CLIENT_SECRET`
   - `GOOGLE_REDIRECT_URI`
   - `SESSION_SECRET`
   - optional `GOOGLE_ALLOWED_DOMAINS`
4. For Google OAuth, set the authorized redirect URI to:
   `https://YOUR-RAILWAY-DOMAIN/auth/callback`
5. Redeploy after changing variables.

Never commit `.env` files or API secrets.
