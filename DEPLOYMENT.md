# Deploying Textropy to a VPS

Target setup: the domain `textropy.dev` pointed at a VPS, nginx on the host as reverse
proxy, certbot for HTTPS, and both app services running as containers from `compose.yml`.

Everything is served from **one origin**: `https://textropy.dev` for the UI and
`https://textropy.dev/api/` for the backend. The frontend owns no `/api` route
(`frontend/app/` is just `layout.tsx` + `page.tsx`), so nginx can hand that whole prefix
to FastAPI, and `lib/api.ts` already builds `${PUBLIC_API_URL}/api/v1/...`. Single origin
also means every request is same-origin, so CORS never enters the picture and one
certificate covers the app.

These steps pick up immediately after:

```bash
git clone git@github.com:cyruscsc/textropy.git
```

## 0. Before you start

DNS `A` record for `textropy.dev` (and `www`) pointing at the VPS, propagated — certbot
fails without it. On the host: Docker Engine + the Compose plugin, `nginx`, and `certbot`
+ `python3-certbot-nginx`.

## 1. Configure `.env`

```bash
cd textropy
cp .env.example .env
```

Edit it to:

```bash
BIND_ADDRESS=127.0.0.1          # containers listen on loopback only; nginx is the only way in
API_PORT=8000
FRONTEND_PORT=3000

PUBLIC_API_URL=https://textropy.dev     # baked into the client bundle at build time
FRONTEND_ORIGIN=https://textropy.dev    # backend CORS allowlist

MODEL_LOADING=eager
EAGER_TIERS=[1]                 # [1,2,3] if you'd rather pay ~90s at startup than on first Tier 2/3 request
MAX_TEXT_CHARS=20000
TORCH_NUM_THREADS=2             # set to the box's core count
API_MEMORY_LIMIT=3g
FRONTEND_MEMORY_LIMIT=512m
```

Writing `https://` here before the certificate exists is fine — it's only a string in a
bundle. It just means the site won't work until step 4.

## 2. Build and start

```bash
docker compose up -d --build
docker compose ps          # wait for api to report (healthy)
docker compose logs -f api
```

First build is the slow one: torch plus baking the HF weights into the api image, and
`npm ci` + `next build` for the frontend. Budget 10–20 minutes and a couple of GB of free
RAM and disk. On a 1 GB VPS the `next build` step is the one that gets OOM-killed — add
swap first if that's what you're on.

## 3. Smoke-test before touching nginx

```bash
curl -s localhost:8000/api/v1/health
curl -sI localhost:3000
ss -tlnp | grep -E '3000|8000'    # must show 127.0.0.1, not 0.0.0.0
```

That last check matters: Docker's published ports write DNAT rules that bypass `ufw`
entirely, so a `0.0.0.0` bind would be world-reachable no matter what your firewall says.
`BIND_ADDRESS=127.0.0.1` is what actually closes it.

## 4. nginx server block

`/etc/nginx/sites-available/textropy.dev`:

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name textropy.dev www.textropy.dev;

    client_max_body_size 1m;

    # No trailing slash on proxy_pass, so /api/v1/... reaches FastAPI unchanged.
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Tier 3 runs synchronously in-request. nginx's 60s default read timeout will
        # cut a long perplexity request off mid-flight and return 504.
        proxy_read_timeout 180s;
        proxy_send_timeout 180s;
        proxy_buffering off;
    }

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/textropy.dev /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default    # else it may win as the default server
sudo nginx -t && sudo systemctl reload nginx
curl -I http://textropy.dev                    # confirm plain HTTP works first
```

## 5. Certificate

```bash
sudo certbot --nginx -d textropy.dev -d www.textropy.dev
```

Certbot rewrites the block in place: adds the `listen 443 ssl` server, the cert paths, and
an HTTP→HTTPS redirect. Then confirm renewal is wired up:

```bash
sudo certbot renew --dry-run
systemctl status certbot.timer
```

## 6. Firewall and reboot survival

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'    # 80 + 443 only; 3000/8000 stay loopback
sudo ufw enable

sudo systemctl enable docker   # restart: unless-stopped brings both services back after reboot
```

## 7. Verify end to end

```bash
curl -s https://textropy.dev/api/v1/health
curl -s https://textropy.dev/api/v1/features | head -c 200
curl -sI https://textropy.dev
curl -sI https://textropy.dev/docs      # expect 404 — production unmounts the docs
```

In the health payload, every entry under `models` should read `loaded`. `coref` is the one
model allowed to report `error` without holding readiness down — it means the image was
built without the `coref` extra, and only the Tier 2 `coreference` feature degrades.

Then load it in a browser, run a Tier 1 analysis, and check the Network tab shows
`POST https://textropy.dev/api/v1/analyze` succeeding. If the UI renders but every
analysis fails, the bundle was built with the wrong `PUBLIC_API_URL` — fix `.env` and
rebuild, since a restart won't change it.

## Redeploying later

```bash
cd textropy && git pull && docker compose up -d --build
```

Two things to keep in mind afterward: if you ever split the API onto `api.textropy.dev`,
that's a `PUBLIC_API_URL` change and therefore a frontend rebuild plus a cert covering the
new name; and because everything is same-origin here, `FRONTEND_ORIGIN` is doing nothing
for browser traffic — it only matters if something calls the API cross-origin later.
