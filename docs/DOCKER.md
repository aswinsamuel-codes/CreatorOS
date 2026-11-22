# Running CreatorOS with Docker

Docker packages CreatorOS with Python, FFmpeg and every library it needs, so it runs the same
way on Windows, macOS, Linux, a home server, a lab cluster or a cloud VM, with one command.

## Quick start

1. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows/macOS) or
   Docker Engine + Compose (Linux).
2. Get the code and start it:

   ```bash
   git clone https://github.com/aswinsamuel-codes/CreatorOS
   cd CreatorOS
   docker compose up -d
   ```

3. Open **http://localhost:8787** and connect your platforms on the **Connections** tab.

Optional: create a `.env` (copy `.env.example`) for keys and set your timezone, e.g.
`TZ=Asia/Kolkata`, so the daily schedule runs at your local times.

## Everyday commands

| Task | Command |
|---|---|
| Start | `docker compose up -d` |
| Logs | `docker compose logs -f` |
| Stop | `docker compose down` |
| Update to a new version | `git pull && docker compose up -d --build` |
| Use the published image instead of building | `docker compose pull && docker compose up -d` |
| Run a CLI command | `docker compose exec creatoros python -m creatoros list` |
| Health | `docker inspect --format '{{.State.Health.Status}}' creatoros` |

## Your data

Everything you create lives in folders next to `docker-compose.yml`, mounted into the container,
so rebuilding or updating the container never loses anything:

| Folder | Contains |
|---|---|
| `data/` | database, connections/keys, your settings (`config.local.yaml`) |
| `workspace/` | generated posts and media |
| `profile/` | your profile, notes and documents |
| `logs/` | log files |

Back up these four folders and you've backed up CreatorOS.

## Folder → post and Video → post

The container can only see folders you share with it. Uncomment and edit the lines in
`docker-compose.yml`:

```yaml
    volumes:
      - D:/Certificates:/media/certificates:ro
      - D:/Videos:/media/videos:ro
```

Then use the **container path** in the dashboard, e.g. `/media/certificates`.

## Local AI models

- **Ollama in Docker:** `docker compose --profile local-ai up -d`, then
  `docker compose exec ollama ollama pull gemma3:12b`, and set the Ollama provider URL to
  `http://ollama:11434/v1` (Settings → Models → Providers).
- **Ollama / LM Studio on your computer:** use `http://host.docker.internal:11434/v1`.
- **Your lab cluster:** use its address as usual, e.g. `http://192.168.1.50:11434/v1`.

## Opening the dashboard to your network

By default the dashboard is reachable only from the same computer (`127.0.0.1:8787`). To use it
from other devices, change the port line to `"8787:8787"` **and** set `DASHBOARD_TOKEN` in `.env`,
then open `http://<server-ip>:8787/?token=<your token>`. For LinkedIn/YouTube logins, add that
address's callback URL in your LinkedIn/Google app too.

## Speech-to-text for videos

The default image skips faster-whisper to stay small. Build with it:

```bash
docker build --build-arg WITH_WHISPER=true -t creatoros:whisper .
```

and set `image: creatoros:whisper` in `docker-compose.yml`.

## How the image is built

- **Multi-stage build:** dependencies are installed into a virtualenv in a builder stage and
  copied into a slim runtime image (no compilers or pip caches in the final image).
- **Non-root:** runs as user `creator` (uid 1000).
- **Health check** on `/api/status`.
- **Secrets never baked in:** `.dockerignore` excludes `.env`, your settings, profile, notes,
  documents and generated content; keys come from `.env` or the dashboard at runtime.
- **CI:** every push runs the test suite, builds the image, starts it and checks the dashboard
  answers (`.github/workflows/ci.yml`). Version tags publish multi-arch images (amd64 + arm64) to
  GitHub Container Registry (`.github/workflows/release.yml`).

## Troubleshooting

- **Linux: permission denied on `data/`.** The container runs as uid 1000. Run
  `sudo chown -R 1000:1000 data workspace profile logs`, or add `user: "${UID}:${GID}"` to the service.
- **Schedule runs at the wrong time.** Set `TZ` in `.env` (e.g. `TZ=Asia/Kolkata`) and restart.
- **Port 8787 already in use.** Stop the non-Docker CreatorOS, or change the host port, e.g.
  `"127.0.0.1:8790:8787"`.
