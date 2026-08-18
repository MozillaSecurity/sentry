"""Tests for moz_sec_sentry."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest

from moz_sec_sentry import _add_system_context, init

if TYPE_CHECKING:
    from pytest_mock import MockerFixture
    from sentry_sdk.types import Event, Hint

TASKCLUSTER_VARS = (
    "RUN_ID",
    "SENTRY_DSN",
    "TASK_ID",
    "TASKCLUSTER_FUZZING_POOL",
    "TASKCLUSTER_ROOT_URL",
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove any ambient config so tests do not inherit the host environment."""
    for var in TASKCLUSTER_VARS:
        monkeypatch.delenv(var, raising=False)


def _event() -> Event:
    """Build an empty event to pass through the before_send hook."""
    return cast("Event", {})


def _hint(**kwargs: object) -> Hint:
    """Build a hint dict to pass through the before_send hook."""
    return cast("Hint", dict(kwargs))


def _traceback_hint() -> Hint:
    """Build a hint carrying a real traceback raised from this module."""
    with pytest.raises(RuntimeError) as excinfo:
        raise RuntimeError("boom")
    return _hint(exc_info=(excinfo.type, excinfo.value, excinfo.tb))


def test_system_stats_added() -> None:
    """System Stats context is always populated."""
    result = _add_system_context(_event(), _hint())
    stats = result["contexts"]["System Stats"]
    assert set(stats) == {"Memory free (MB)", "Disk free (MB)", "OS"}
    assert isinstance(stats["Memory free (MB)"], int)
    assert isinstance(stats["Disk free (MB)"], int)
    assert stats["OS"]


def test_taskcluster_empty_without_env() -> None:
    """Taskcluster context exists but stays empty when no task vars are set."""
    result = _add_system_context(_event(), _hint())
    assert result["contexts"]["Taskcluster"] == {}


def test_taskcluster_context(monkeypatch: pytest.MonkeyPatch) -> None:
    """Task ID and a browsable task URL are recorded."""
    monkeypatch.setenv("TASK_ID", "abc123")
    monkeypatch.setenv("TASKCLUSTER_ROOT_URL", "https://tc.example.com")
    monkeypatch.setenv("RUN_ID", "2")
    result = _add_system_context(_event(), _hint())
    assert result["contexts"]["Taskcluster"] == {
        "Task ID": "abc123",
        "Task URL": "https://tc.example.com/tasks/abc123/runs/2",
    }


def test_taskcluster_context_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Root URL and run ID fall back to 'unknown' when unset."""
    monkeypatch.setenv("TASK_ID", "abc123")
    result = _add_system_context(_event(), _hint())
    assert (
        result["contexts"]["Taskcluster"]["Task URL"]
        == "unknown/tasks/abc123/runs/unknown"
    )


def test_fuzzing_pool(monkeypatch: pytest.MonkeyPatch) -> None:
    """The fuzzing pool is recorded independently of the task ID."""
    monkeypatch.setenv("TASKCLUSTER_FUZZING_POOL", "pool-42")
    result = _add_system_context(_event(), _hint())
    assert result["contexts"]["Taskcluster"] == {"Fuzzing Pool": "pool-42"}


def test_origin_module_tag() -> None:
    """The module raising the exception is tagged for issue grouping."""
    result = _add_system_context(_event(), _traceback_hint())
    assert result["tags"]["origin_module"] == __name__


def test_origin_module_tag_preserves_existing() -> None:
    """An existing tags dict is extended, not replaced."""
    event = cast("Event", {"tags": {"keep": "me"}})
    result = _add_system_context(event, _traceback_hint())
    assert result["tags"]["keep"] == "me"
    assert result["tags"]["origin_module"] == __name__


@pytest.mark.parametrize(
    "hint_kwargs",
    [{}, {"exc_info": None}],
    ids=["no-exc-info", "null-exc-info"],
)
def test_no_origin_module_without_traceback(hint_kwargs: dict[str, object]) -> None:
    """Events without exception info are left untagged rather than raising."""
    result = _add_system_context(_event(), _hint(**hint_kwargs))
    assert "tags" not in result


def test_init_without_dsn(mocker: MockerFixture) -> None:
    """init() is a no-op when SENTRY_DSN is unset."""
    sentry_init = mocker.patch("moz_sec_sentry.sentry_init")
    init()
    assert not sentry_init.called


def test_init_skipped_under_pytest(
    monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
) -> None:
    """init() refuses to report while running under pytest."""
    monkeypatch.setenv("SENTRY_DSN", "https://key@example.com/1")
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test")
    sentry_init = mocker.patch("moz_sec_sentry.sentry_init")
    init()
    assert not sentry_init.called


def test_init_enabled(monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    """init() configures the SDK with the DSN and the context hook."""
    monkeypatch.setenv("SENTRY_DSN", "https://key@example.com/1")
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    sentry_init = mocker.patch("moz_sec_sentry.sentry_init")
    init()
    sentry_init.assert_called_once_with(
        dsn="https://key@example.com/1",
        before_send=_add_system_context,
    )
