# Testing notes

Things about this suite that are not obvious, and that have cost time.

## Migrations never run in the test suite

`tests/conftest.py` builds the schema from the models with `create_all` against in-memory
SQLite. Alembic is never invoked. On top of that, the migration chain **cannot** run on
SQLite at all — it stops at 0016, which uses an `ALTER` SQLite does not support.

So a divergence between a model and its migration leaves the whole suite green and only
shows up on deploy.

**Verify migrations on staging.** Any push to a branch other than `main` deploys to
staging, which runs `alembic upgrade head` against real Postgres before the service starts.
That is currently the only place migrations execute.

## Coverage under-reports some modules, and we do not know why

Observed while building the helpdesk integration:
`app/services/support/settings.py` reported **32%** for a test that demonstrably executes
it — the response body carries a message that exists nowhere else in the codebase, and
`module.__file__` confirmed the same file. Adding one direct service-level test, exercising
a fraction of the file, moved the number to **83%** without asserting anything new.

Ruled out:

| Suspected | Result |
|---|---|
| Coverage config or exclusions | There are none — `pyproject.toml` has no `[tool.coverage]` |
| Dotted-module resolution (`--cov=app.services.support.settings`) | `--cov=app` reports the same |
| Duplicate `settings.py` basenames confusing file mapping | The other two report their own, uninflated numbers |
| Nothing inside HTTP request handling is traced | `app/api/v1/knowledge.py` reports 96% from API tests |

Not established: why this module specifically.

**What to take from a coverage number here:** it is a floor, not a measure. A **0%** is worth
acting on immediately — that is how `app/services/ai/reembed.py` was found untested after it
had already failed in production. A number below 100% on a module reached through the API
is not, on its own, evidence that anything is untested. Check which behaviours have
assertions before writing tests to move a number; rewriting API tests as service tests to
reach 100% would trade away the parts that check status codes, permissions and wiring.
