# Railway setup

1. Create a new Railway project from the GitHub repository.
2. Railway will use the included Dockerfile and start command:
   `python start.py`.
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

## Persistent projects on Railway

Railway containers can be rebuilt. To keep uploaded documents, projects and generated outputs after redeploys:

1. Add a Railway Volume.
2. Mount it at `/data`.
3. Add this Railway variable:
   - `STORAGE_DIR=/data`
4. Redeploy.

Without a volume, the app works, but project files created inside the container may disappear after rebuilds.

Never commit `.env` files or API secrets.
