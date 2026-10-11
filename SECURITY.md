# Security policy

Sclerotin is a reference that people copy into their own deployments, so a weakness here is a weakness there too. Reports are welcome.

## Reporting a vulnerability

Report privately through GitHub: open the [Security tab](https://github.com/xinitd/sclerotin/security) and click **Report a vulnerability**. Please don't open a public issue or pull request for a security problem.

A useful report names the file and setting involved, shows how to reproduce the problem and says what an attacker gains.

## Scope

In scope:

- The configuration in this repository: `webserver/default.conf`, `docker-compose.yaml`, `Dockerfile`, `main.py` and `static/`
- The demo at https://sclerotin.args.tech, which runs the code from this repository
- Mistakes in the README that would weaken a deployment that follows it

Out of scope:

- Limitations the README already describes, such as rate limits that count addresses rather than IPv6 prefixes, or a client that keeps trickling a request body
- Problems that appear only after the documented setup is changed, for example behind a CDN proxy or with `DOCS_ENABLED=true` in production
- Bugs in FastAPI, Nginx, Python or other upstream projects: report those upstream. If Sclerotin's configuration is what makes one exploitable, it is in scope
- Scanner output without a demonstrated impact

## Testing the demo

Manual testing of the demo is welcome. Please keep automated tools at a low rate and don't run denial-of-service tests against it.

## Supported versions

Fixes land in `main` and ship in the next release. Older releases don't get backports.

## After a report

A first reply usually comes within a week. A confirmed issue is fixed and published as a GitHub security advisory, with credit to the reporter unless they prefer otherwise. There is no bug bounty.
