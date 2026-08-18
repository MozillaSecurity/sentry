"""Common config for Sentry for Fuzzing tools"""

import os
from platform import system
from shutil import disk_usage

from psutil import virtual_memory
from sentry_sdk import init as sentry_init
from sentry_sdk.types import Event, Hint


def _add_system_context(event: Event, hint: Hint) -> Event:
    event.setdefault("contexts", {})
    event["contexts"]["System Stats"] = {
        "Memory free (MB)": virtual_memory().available // 1024 // 1024,
        "Disk free (MB)": disk_usage("/").free // 1024 // 1024,
        "OS": system(),
    }
    event["contexts"]["Taskcluster"] = {}

    if "TASK_ID" in os.environ:
        task_id = os.environ["TASK_ID"]
        root_url = os.environ.get("TASKCLUSTER_ROOT_URL", "unknown")
        run_id = os.environ.get("RUN_ID", "unknown")
        event["contexts"]["Taskcluster"]["Task ID"] = task_id
        event["contexts"]["Taskcluster"]["Task URL"] = (
            f"{root_url}/tasks/{task_id}/runs/{run_id}"
        )

    if "TASKCLUSTER_FUZZING_POOL" in os.environ:
        event["contexts"]["Taskcluster"]["Fuzzing Pool"] = os.environ[
            "TASKCLUSTER_FUZZING_POOL"
        ]

    # add crashing module as a tag
    exc_info = hint.get("exc_info")
    if exc_info:
        _, _, tb = exc_info
        if tb:
            mod_name = tb.tb_frame.f_globals.get("__name__")
            if mod_name:
                event.setdefault("tags", {})["origin_module"] = mod_name

    return event


def init() -> None:
    """Common config for Sentry for Fuzzing tools"""
    if "SENTRY_DSN" in os.environ and "PYTEST_CURRENT_TEST" not in os.environ:
        sentry_init(
            dsn=os.environ["SENTRY_DSN"],
            before_send=_add_system_context,
        )
