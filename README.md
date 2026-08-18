# moz-sec-sentry

Common config for [Sentry](https://sentry.io/) for Fuzzing tools.

This package centralises the Sentry setup shared by Mozilla's fuzzing tools, so
each tool gets identical error reporting and the same extra diagnostic context
attached to every event.

## Install

```sh
pip install moz-sec-sentry
```

> **Note:** the distribution is named `moz-sec-sentry` rather than `sentry`,
> because that name belongs to Sentry itself on PyPI. The module matches:
> `import moz_sec_sentry`.

## Usage

Call `init()` once, as early as possible in your program's startup:

```python
from moz_sec_sentry import init

init()
```

`init()` is a no-op unless the `SENTRY_DSN` environment variable is set, so it
is safe to call unconditionally — tools can ship the call and only enable
reporting where a DSN is configured. It is also deliberately a no-op while
running under pytest (detected via `PYTEST_CURRENT_TEST`) so test suites never
report to Sentry.

## Configuration

| Variable | Purpose |
| --- | --- |
| `SENTRY_DSN` | The Sentry DSN to report to. Reporting is disabled if unset. |
| `TASK_ID` | Taskcluster task ID, used to build a link back to the task. |
| `TASKCLUSTER_ROOT_URL` | Taskcluster deployment root URL. Defaults to `unknown`. |
| `RUN_ID` | Taskcluster run ID. Defaults to `unknown`. |
| `TASKCLUSTER_FUZZING_POOL` | Name of the fuzzing pool the task belongs to. |

## Event context

Every event is enriched via a `before_send` hook with:

- **System Stats** — free memory (MB), free disk (MB), and OS name.
- **Taskcluster** — task ID, a direct task URL, and the fuzzing pool, when the
  corresponding environment variables are present.
- An `origin_module` tag naming the module the exception was raised from, which
  makes it possible to group issues by the component at fault.
