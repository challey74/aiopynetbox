# Contributing

Thanks for your interest in aiopynetbox.

## Development setup

The project is managed with [uv](https://docs.astral.sh/uv/) and requires
Python 3.11+:

```sh
uv sync              # install the environment
uv run pytest        # run the test suite
uv run ruff check    # lint
uv run ruff format   # format
uv run pyright       # type check
```

All four checks run in CI and must pass.

## Testing conventions

Tests run entirely against `FakeNetbox` in `tests/conftest.py`, an
in-memory NetBox served through `httpx2.MockTransport`. Tests never touch
the network and never require a real NetBox instance. If your change needs
an endpoint or behavior the fake doesn't model yet, extend the fake.

New features and bug fixes should come with tests.

`src/aiopynetbox/apps_generated.py` and `src/aiopynetbox/hints_generated.pyi` are generated - don't edit them by hand. To
refresh the endpoint hints (e.g. after a NetBox release), run
`uv run python scripts/generate_endpoints.py` and commit the diff; a
scheduled workflow also does this weekly against demo.netbox.dev.

## Design constraints

This library deliberately differs from pynetbox: all I/O is explicit and
awaitable. Before proposing API changes, read the design constraints in
[AGENTS.md](AGENTS.md), particularly the list of pynetbox behaviors that
must not be replicated (lazy attribute fetches, `len()` that does I/O,
properties that make requests).

## Commits and pull requests

- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/)
  (`feat:`, `fix:`, `docs:`, `ci:`, `chore:`, ...).
- Keep changes focused; unrelated refactoring belongs in its own PR.
- User-visible changes get a line in `CHANGELOG.md` under Unreleased.
