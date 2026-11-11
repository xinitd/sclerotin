# Contributing

Sclerotin is a reference: every setting in it is there for a reason, and the README says which. Changes that keep it that way are welcome.

## Bugs and suggestions

Open an [issue](https://github.com/xinitd/sclerotin/issues). For a bug, name the file and setting involved, what you expected and what happened instead, with the commands or requests that show it. For a suggestion, describe the problem it solves in a deployment.

Security problems don't go to issues: report them privately, as [SECURITY.md](SECURITY.md) describes.

## Pull requests

1. Fork the repository and branch off `main`, with a type prefix in the branch name: `fix/`, `docs/`, `ci/`, `test/`.
2. One change per pull request.
3. Open it against `main`. CI has to pass: the image build and dependency check, ruff and the tests.
4. I review every pull request and merge it once it is ready and CI is green.

## What a change needs

- **Tests.** New behavior comes with tests in `tests/`, and so does every change to a route or a security header. CI fails if any line or branch of `main.py` is left untested.
- **Lint.** `ruff check .` passes with the rules in `ruff.toml`.
- **Both copies of a header.** A security header changed in `main.py` changes in `webserver/default.conf` too. A test compares them.
- **An explanation.** A setting that changes how a deployment behaves gets a sentence in the README on why it is there.
- **Exact pins.** A new dependency is pinned to an exact version: a runtime one in `requirements.txt`, which has to match the image, a tool in `requirements-dev.txt`.

## Checks on your machine

```
python3 -m venv env
. env/bin/activate
pip install -r requirements-dev.txt
ruff check .
pytest
```

Coverage as CI measures it:

```
coverage run --branch --source=main -m pytest
coverage report --show-missing
```

CI covers the Python side only. A change to `webserver/default.conf`, `docker-compose.yaml` or the `Dockerfile` also needs a run of the whole stack, as in [Local development](README.md#local-development), and the checks in [After an update](README.md#after-an-update).

## License

Contributions are accepted under the [MIT License](LICENSE), the license of the project.
