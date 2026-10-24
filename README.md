# Sclerotin

<img src="static/logo.jpeg" alt="Sclerotin logo" width="300">

A hardened reference deployment of FastAPI behind Nginx with Docker Compose: strict CSP, security headers, isolated container networks, read-only containers and TLS with post-quantum key exchange. Running at [sclerotin.args.tech](https://sclerotin.args.tech/).

The application is a single endpoint, `/api/v1/ping`, and is trivial on purpose: the project is everything around it. It is not a framework, a library or an application template, but a reference for the parts that usually get decided in a hurry: the proxy, the container, the network and the headers. Every choice is explained in [How it works](#how-it-works).

## Features

- A Content Security Policy per kind of response: `default-src 'none'` for the API, a policy of its own for the landing page, a relaxed one for the docs only while they are switched on ([Headers and CSP](#headers-and-csp))
- Security headers split between Nginx and the app, error responses included: the app answers its own unhandled exceptions, and Nginx adds the app's headers to the errors it generates itself ([Headers and CSP](#headers-and-csp))
- The app on an internal network with no route out of the host ([Networks](#networks))
- Read-only root filesystems, all capabilities dropped, `no-new-privileges`, memory, CPU and PID limits, an unprivileged app user ([Containers](#containers))
- Unknown host names and bare-IP requests dropped without an answer ([Unknown hosts](#unknown-hosts))
- Per-address rate limits that see real IPv6 addresses, request size limits and timeouts against slow clients ([Limits](#limits), [Networks](#networks))
- TLS 1.2 and 1.3 with Mozilla's intermediate profile, post-quantum hybrid key exchange and HSTS; Let's Encrypt with automatic renewal ([TLS](#tls), [Let's Encrypt](#lets-encrypt))
- The base images and every Python dependency are pinned, with weekly Dependabot pull requests ([Updating](#updating))

## Requirements

Docker Engine 27 or later and Compose 2.17 or later: the setup relies on per-network IPv6 without a daemon-wide subnet and on `ip6tables` being enabled by default, both of which came with Engine 27, and on `restart` inside `depends_on`, which came with Compose 2.17. The daemon has to run as root and without `userns-remap`: otherwise root in the container is an unprivileged user on the host and can't read the root-owned private key.

## Local development

```
git clone https://github.com/xinitd/sclerotin.git
cd sclerotin
cp .env.example .env
```

Optional settings (docs, resource limits) go to `.env`, which Compose reads automatically. Set `DOCS_ENABLED=true` there to turn on Swagger UI and ReDoc.

Nginx needs a certificate, and `webserver/*.pem` is gitignored, so a fresh clone has none. Generate a self-signed one (`-noenc` needs OpenSSL 3; on 1.1.1 it is `-nodes`):

```
openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:P-256 -noenc -days 365 \
  -keyout webserver/privkey.pem -out webserver/fullchain.pem \
  -subj '/CN=sclerotin.args.tech' \
  -addext 'subjectAltName=DNS:sclerotin.args.tech,DNS:localhost,IP:127.0.0.1'
sudo chown root:root webserver/privkey.pem
```

The `chown` is explained in [Containers](#containers): the Nginx master can't read a key owned by anyone else. Without both files Compose refuses to start, naming the missing path.

```
docker compose up -d --build
```

Open `https://localhost` and accept the certificate warning, or use `curl -k`: `https://127.0.0.1` sends no SNI and is rejected.

### Without Docker

For local development without Nginx:

```
python3 -m venv env
. env/bin/activate
pip install -r requirements.txt
DOCS_ENABLED=true uvicorn main:app --host 127.0.0.1 --port 8000
```

`127.0.0.1` keeps the dev server off the network. It is Uvicorn's default; the flag makes it explicit. `DOCS_ENABLED=true` turns on `/docs` and `/redoc`.

## Production

The server needs Docker as above, ports 80 and 443 open, and `sclerotin.args.tech` resolving to it directly, not to a CDN proxy (on Cloudflare, a DNS-only record). Behind a proxy, clients get its TLS settings and extra headers, and Nginx sees the proxy's addresses instead of the clients', in the logs and in the rate limit.

Deploy with Git: `.env` is gitignored, so local settings like `DOCS_ENABLED=true` don't reach the server, and without it the defaults apply, which is what production uses. Copying the directory with `scp` or `rsync` would carry `.env` along.

```
git clone https://github.com/xinitd/sclerotin.git
cd sclerotin
```

Generate the self-signed certificate as in [Local development](#local-development) and run `docker compose up -d --build`: the Certbot hooks below stop and start a running `webserver`, so the stack has to be up before the first certificate is issued. Don't open `https://sclerotin.args.tech` in a browser until then: `args.tech` is HSTS-preloaded with subdomains, so the certificate warning can't be bypassed (`curl -k` is fine).

Five lines of `static/index.html` belong to this deployment rather than to the project: the `canonical` address, `og:url`, `og:image`, the domain in the `curl` command and the footer. On another domain, change them along with `server_name` in `webserver/default.conf`.

### Let's Encrypt

Certbot runs on the host, not in a container: install the distribution package (`sudo apt install certbot` on Debian and Ubuntu), which also brings `certbot.timer`, a systemd timer that runs `certbot renew` twice a day. From the repository directory:

```
sudo certbot certonly --standalone -d sclerotin.args.tech \
  --pre-hook "docker compose -f $PWD/docker-compose.yaml stop webserver" \
  --post-hook "docker compose -f $PWD/docker-compose.yaml start webserver"
ln -sf /etc/letsencrypt/live/sclerotin.args.tech/{fullchain,privkey}.pem webserver/
docker compose restart webserver
```

`--standalone` answers the challenge with Certbot's own server on port 80, so the hooks stop Nginx while it runs: the site is down for a few seconds at each renewal, and neither the stack nor `default.conf` needs anything for the challenge. Certbot stores the hooks with the certificate and runs them only when it actually requests one, not on every timer run. `$PWD` is expanded by the shell, so the stored hooks carry the absolute path the timer needs.

The symlinks keep the paths Compose mounts, so `docker-compose.yaml` stays as it is. No `chown` either: Certbot creates its keys as `root:root 600`. Docker resolves a bind-mounted symlink when the container starts and keeps that file until the next start, so after a renewal `nginx -s reload` would keep serving the old certificate; the post-hook's `start` is what picks up the new one.

Check the renewal once: `sudo certbot renew --dry-run` renews against the staging server without replacing the certificate and runs both hooks, so the site goes down briefly here too, and `systemctl list-timers certbot.timer` shows the next run.

### After the first deploy

Open the site from another machine once: requests from the server itself reach the published ports through `docker-proxy`, so they prove nothing about the outside. The two networks on Nginx are no risk here: Docker publishes ports on the network that gives the container its default gateway, and it never picks an `internal` network for that.

Once the domain has an AAAA record, check that IPv6 clients keep their addresses: `curl -6 https://sclerotin.args.tech/api/v1/ping`, then `docker compose logs webserver | tail -n 1` - the logged address has to be the client's.

## Updating

Deploy updates with `git pull` and `docker compose up -d --build`, without a service name. Nginx resolves `app` to an IP once at startup, and a recreated `app` container may get a new IP; `restart: true` inside `depends_on` (Compose >= 2.17) restarts `webserver` whenever `app` is recreated. `docker compose up -d --build app` limits the run to `app`, so Nginx is not restarted and may keep proxying to the old IP (502).

That command never changes the base images on its own: both are pinned by digest, Nginx in `docker-compose.yaml` and Python in the `Dockerfile`. A tag is not enough: the build checks it against Docker Hub every time, so a `python:3.14.8-slim` rebuilt upstream would reach the server without passing CI. With the digest, every build uses the base image CI tested, and a newer build comes as a Dependabot pull request that changes the digest. The tag in front of the digest is there for people and for Dependabot: Docker pulls by the digest.

Changing the network options means the network has to be recreated: after a change to `networks:` in `docker-compose.yaml`, run `docker compose down` before `up`.

After a change to `webserver/default.conf`, also run `docker compose restart webserver`: Compose compares service definitions and images, not the contents of mounted files, so `up` doesn't restart Nginx for it. `nginx -s reload` is not enough either: `git pull` replaces the file rather than rewriting it, and the container keeps the file it was started with.

`requirements.txt` pins the full dependency set tested in the image, so every build installs the same versions, and their security updates don't arrive on their own either. Only `pydantic-core` is not listed: `pydantic` already pins it to an exact version, and a line of its own would get separate Dependabot pull requests that conflict with that pin and break the build. `.github/dependabot.yml` asks Dependabot for weekly pull requests for `requirements.txt`, for the base image of the `Dockerfile` and for the Nginx image in `docker-compose.yaml`. To upgrade by hand, in a clean venv: `pip install -U fastapi uvicorn && pip freeze --exclude pydantic-core > requirements.txt`, then rebuild and retest.

Dependabot changes only the line of the package it updates, so a release that brings in a new dependency would install it unpinned. `.github/workflows/ci.yml` catches that on every pull request and every push to `main`: it builds the image, compares `pip freeze --exclude pydantic-core` inside it with `requirements.txt` and fails with the diff. It covers the Python side only: an Nginx update still has to be checked on a running deployment. The workflow's only action is pinned by commit SHA, and Dependabot updates it as well.

### After an update

`git pull` prints the range it applied, such as `Updating 647412b..f80512f`: the first commit is the version to return to. If a check below fails, `git checkout` that commit and run `docker compose up -d --build`, with the extra steps above if `default.conf` or `networks:` changed. Once a fix is merged, `git switch main` and update as usual.

Check what the server runs, not only what CI built: the server builds its own image, and an update that didn't apply, such as `docker compose up -d` without `--build`, shows up only here.

```
docker compose ps
docker compose exec app python --version
docker compose exec app pip freeze --no-cache-dir
```

`app` has to be `(healthy)`, and the list has to match `requirements.txt` plus `pydantic_core`. When only the app changed, a `webserver` created days ago but up for minutes is expected: `restart: true` restarts Nginx without recreating it. An ID instead of `sclerotin-app` in the IMAGE column means the tag moved after the container was created, for example by a separate `docker compose build`: with the containerd image store, each build gets a new image ID even when the content is the same, because its provenance attestation differs, and the next `docker compose up -d --build` recreates the container. `--no-cache-dir` only silences a warning: `appuser` has no home directory and the filesystem is read-only, so pip has nowhere to keep a cache.

Then check from another machine, for the reason given in [After the first deploy](#after-the-first-deploy). `curl -sI https://sclerotin.args.tech/api/v1/ping` has to return `200` with every security header exactly once: a duplicate means an Nginx fallback from `default.conf` was added next to the app's own header. In a browser, open the site with an empty cache, so it loads the new `style.css` and `headers.js` rather than cached copies, and check the console for CSP errors.

Once the checks pass, clean up what the previous build left behind:

```
docker image prune
docker builder prune -a
```

The first removes images with no name, the second the whole build cache, so the next build runs every step again. Neither removes the previous Nginx image: Compose pulls it by digest, and Docker counts the digest as its name, so the image is not dangling even though `docker system df -v` lists it as `<none>`. The running Nginx is listed as `<none>` too, with 1 in the CONTAINERS column. Remove the old one by the digest the update replaced, from the removed line in the pull request or in `git log -p docker-compose.yaml`:

```
docker image rm nginx@sha256:<old digest>
```

`docker system df` then shows nothing reclaimable. `docker image prune -a` would remove the old Nginx image as well, but along with every other image that has no container.

## Sizing

The limits fit this demo: one endpoint on a small server. A project with real traffic has to size them by hand, since none of them adjusts on its own:

- **CPU and memory.** `.env` sets `APP_CPUS`, `APP_MEM_LIMIT`, `WEBSERVER_CPUS` and `WEBSERVER_MEM_LIMIT`. Under load the CPU quota usually runs out first, and the kernel then throttles the container.
- **Nginx workers.** Their number follows the host's CPUs, not `WEBSERVER_CPUS` ([Containers](#containers)): match it with `cpuset` or with `worker_processes` in an `nginx.conf` of your own. Each worker handles at most 1024 connections (`worker_connections` in the image's `nginx.conf`), and a proxied request takes two of them, one from the client and one to `app`. Raising that limit also takes your own `nginx.conf`, because `default.conf` is included inside the `http` block and can't reach `events`; the open-file limit (`worker_rlimit_nofile`) has to grow with it.
- **Process limits.** `pids_limit: 50` is set for both services in `docker-compose.yaml`, not in `.env`. Nginx needs room for the master and its workers, twice the workers during a reload. One Uvicorn process can reach about 42 tasks: AnyIO's thread pool, which serves file responses, holds up to 40 threads. More than one Uvicorn worker therefore needs a higher limit.
- **Request bodies.** The 16 MB tmpfs and `client_max_body_size 1m` ([Limits](#limits)) assume an API without uploads. A project that accepts files needs a larger body limit and a tmpfs that fits its concurrent uploads, with the memory limit raised to match, since the tmpfs counts against it.
- **Rate limit.** 10 requests per second with a burst of 20 applies per address. Users behind one NAT, such as an office network or a mobile carrier, share an address and therefore a bucket, and a page with many assets spends a request on each. Set `rate` and `burst` in `default.conf` for the real traffic.

## How it works

Two containers: `app` runs Uvicorn with `main.py`, `webserver` runs Nginx with `webserver/default.conf`, and `docker-compose.yaml` ties them together.

### Containers

Both containers run with a read-only root filesystem, all capabilities dropped and `no-new-privileges`; Nginx gets back only `CHOWN`, `SETUID` and `SETGID`, plus tmpfs for `/run` and `/var/cache/nginx`. Ports 80 and 443 need no `NET_BIND_SERVICE`: Docker sets `net.ipv4.ip_unprivileged_port_start=0` in the container's network namespace, and the setting covers IPv6 too. Without `DAC_OVERRIDE` the Nginx master is bound by file permissions like an ordinary user, so the private key, readable only by its owner, must belong to root.

`app` gets no capabilities back and runs as an unprivileged user created in the `Dockerfile`, so nothing in it runs as root, even inside the container.

The healthcheck's local requests to `/api/v1/ping` are filtered out of the Uvicorn access log; requests coming through Nginx are still logged.

Nginx starts one worker per CPU it can run on: the image's own `nginx.conf` sets `worker_processes auto`, and `cpus: 0.5` is a share of CPU time rather than a set of CPUs, so it doesn't change the count. Extra workers add no throughput, since they all share that half CPU. `pids_limit: 50` leaves room for the master and 49 workers: on a host with 50 or more CPUs, Nginx logs `fork() failed while spawning "worker process"` and carries on with the workers it could start. A reload starts the new workers before the old ones exit, so it runs into the limit from about 25 CPUs.

On such a host, give `webserver` a `cpuset` in `docker-compose.yaml`, for example `cpuset: "0-1"`: the image is built on Alpine, whose C library counts only the CPUs a process may run on, so `auto` then starts one worker per CPU in the set. Raising `pids_limit` works too. A fixed `worker_processes` takes an `nginx.conf` of your own: the image's autotuning script (`NGINX_ENTRYPOINT_WORKER_PROCESSES_AUTOTUNE`) rewrites that file at startup, which the read-only root filesystem doesn't allow, and `nginx -g` can't override a directive the file already sets.

### Networks

`app` joins only `internal_network`, declared `internal: true`, which has no route out of the host: a compromised app can neither download a payload nor send anything out. Nginx joins that network and `public_network`, which carries the published ports 80 and 443; an internal network can't carry them.

`public_network` is declared `enable_ipv6: true` and every server in `default.conf` listens on `[::]` too, because Docker publishes ports 80 and 443 on IPv6 as well. On an IPv4-only network those connections go through the userland proxy, which opens a new connection from the network gateway: Nginx would then see every IPv6 client as `172.x.0.1`, so they would share one rate-limit bucket and one address in the logs. Docker allocates the ULA subnet and sets up `ip6tables` itself.

`app` listens on `0.0.0.0:8000` inside `internal_network` only: port 8000 is not published, so all traffic goes through Nginx. Uvicorn runs with `--forwarded-allow-ips='*'` and in that mode takes the client IP from the leftmost `X-Forwarded-For` entry, so Nginx overwrites that header with `$remote_addr` instead of appending to it; otherwise a client could spoof its IP.

### Unknown hosts

Nginx serves only `sclerotin.args.tech` and `localhost`; other host names and bare-IP requests are dropped (`444` on HTTP, rejected TLS handshake on HTTPS). A client can also complete the TLS handshake with a valid SNI and then send a foreign `Host` header: over HTTP/2 Nginx rejects that itself with `421`, over HTTP/1.1 the request reaches the catch-all `443` server, which returns `444`. Plain HTTP sent to port 443 is answered by Nginx itself with a `400` page before the catch-all's `return` runs; `error_page 497 /` sends such requests back to that `return`, so they are dropped too.

### Limits

Nginx allows each client address 10 requests per second, with a burst of 20 served without delay. Beyond that it answers `429` instead of the default `503`, so a throttled client can tell the limit from an outage. The limit counts addresses, not clients: an IPv6 client usually holds at least a /64 and can send each request from a new address in it, and Nginx has no built-in way to group addresses by prefix. Request bodies are capped at 1 MB and a single header line at 8 KB. A client has 12 seconds to send its headers and may not pause for longer than that while sending a body, and idle keep-alive connections close after 15 seconds, so a silent client can't hold a connection open.

The body timeout limits pauses, not the whole body: a client that keeps trickling a body keeps its connection, and so does one that reads a response slowly. Meanwhile Nginx keeps a request body over 16 KB, or the rest of a response the client is slow to read, in a temporary file under `/var/cache/nginx`. That directory is a tmpfs: it lives in memory and counts against the container's memory limit, so it is capped at 16 MB. When it is full, the requests that need more room fail instead of Nginx being killed for running out of memory.

### TLS

TLS follows Mozilla's intermediate profile, guidelines version 6.0. `ssl_ecdh_curve` is left unset: the OpenSSL default already includes the post-quantum hybrid X25519MLKEM768, which current browsers negotiate. Session tickets are off, so sessions are resumed from the shared session cache.

HSTS is sent for two years, as Mozilla recommends, with `includeSubDomains` but without `preload`: hstspreload.org accepts only apex domains, and `args.tech` is already preloaded with its subdomains.

### Headers and CSP

Security headers are split between the layers: Nginx sets HSTS, `X-Frame-Options` and `Referrer-Policy`; the app sets CSP, `X-Content-Type-Options` and `Permissions-Policy`. Responses Nginx generates itself (429 from the rate limit, 413, 502 while `app` is down, 504 when it doesn't answer in time) never reach the app, so Nginx adds the app's three headers to any response that lacks them. The app doesn't rely on that fallback for its own errors, so it keeps its headers even without Nginx in front. An unhandled exception would be answered by Starlette's `ServerErrorMiddleware`, which sits outside every middleware the app adds and would send the 500 bare; the middleware in `main.py` catches the exception, logs it and returns the 500 itself. The values are duplicated in `main.py` and `webserver/default.conf`; change both together.

Swagger UI (`/docs`), ReDoc (`/redoc`) and the schema (`/openapi.json`) are off unless `DOCS_ENABLED=true` is set, so in production every response other than the landing page gets the strict CSP (`default-src 'none'; frame-ancestors 'none'`). With docs enabled, only `/docs`, `/redoc` and `/docs/oauth2-redirect` get the relaxed policy Swagger UI and ReDoc need (CDN assets, inline scripts and styles).

### Landing page

`/` serves a static page from `static/`, the only HTML the app returns while the docs are off. It gets a policy of its own: `default-src 'none'` plus `script-src`, `style-src`, `img-src` and `connect-src`, each of them `'self'`. `base-uri`, `form-action` and `frame-ancestors` don't fall back to `default-src`, so they are set to `'none'` explicitly. Its stylesheet and its script are files rather than markup, so the page needs neither `unsafe-inline` nor a nonce.

The script asks this server for `/api/v1/ping` and prints the response, headers and all; without it the block says so and leaves the reader with the `curl` command above it. The page holds no recorded response on purpose, so the header values live in `main.py` and `webserver/default.conf` and nowhere else.

Every file has a route of its own and nothing is mounted: a mounted directory publishes whatever ends up in it, an editor's backup file included, while the routes are an allowlist, like the capabilities and the policies elsewhere. `/favicon.ico` answers `204` for the browsers that ask for it regardless.

Every path other than `/` carries `X-Robots-Tag: noindex`, while `robots.txt` disallows nothing: a crawler has to be allowed to fetch a path before it can see that header.
