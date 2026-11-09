"""Trusted, detached deadline guard; never imports or runs a submission.

The API can die without stopping this process. Its only authority is the exact
random container name supplied by the runner. Docker commands have bounded
timeouts, discard all output, and never pull images or enumerate other jobs.
"""
import argparse
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time


_NAME = re.compile(r"ai-tutor-m1-[0-9a-f]{32}\Z")
_CONTEXT = "desktop-linux"
_ENV_NAMES = ("PATH", "SystemRoot", "SYSTEMROOT", "WINDIR", "TEMP", "TMP",
              "USERPROFILE", "HOME", "APPDATA", "LOCALAPPDATA", "DOCKER_CONFIG")


def _environment(source):
    return {key: value for key, value in source.items()
            if key in _ENV_NAMES and isinstance(value, str)}


def _validate_resource(container_name, docker_binary):
    if not isinstance(container_name, str) or _NAME.fullmatch(container_name) is None:
        raise ValueError("Invalid execution container identity")
    if not isinstance(docker_binary, str) or not Path(docker_binary).is_absolute():
        raise ValueError("Docker binary must be an absolute server-owned path")


class WatchdogHandle:
    def __init__(self, process):
        self.process = process

    def stop(self):
        """Called only after the runner has confirmed container removal."""
        try:
            if self.process.poll() is None:
                self.process.terminate()
            self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            try:
                self.process.kill()
                self.process.wait(timeout=2)
            except (OSError, subprocess.TimeoutExpired):
                pass
        except OSError:
            pass


def start_watchdog(container_name, deadline_unix, docker_binary, docker_env):
    """Start an independent guard before any container create request."""
    _validate_resource(container_name, docker_binary)
    if (type(deadline_unix) not in (int, float) or not math.isfinite(deadline_unix)
            or not 0 < deadline_unix - time.time() <= 600):
        raise ValueError("Invalid execution guard deadline")
    command = [sys.executable, "-I", "-B", str(Path(__file__).resolve()),
               "--container", container_name, "--deadline", str(deadline_unix),
               "--docker", docker_binary]
    options = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL,
               "stderr": subprocess.DEVNULL, "shell": False, "close_fds": True,
               "env": _environment(docker_env)}
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        options["start_new_session"] = True
    return WatchdogHandle(subprocess.Popen(command, **options))


def reap_container(container_name, docker_binary, docker_env, *, attempts=3):
    """Force-remove only this exact resource; a successful daemon ACK confirms removal.

    An unavailable daemon is never interpreted as successful cleanup. A target
    already removed by the normal runner may harmlessly exhaust these retries.
    No output is captured, so a Docker diagnostic cannot grow host buffers or
    leak configuration. The runner journal handles unresolved cleanup later.
    """
    _validate_resource(container_name, docker_binary)
    if type(attempts) is not int or not 1 <= attempts <= 3:
        raise ValueError("Invalid cleanup retry limit")
    environment = _environment(docker_env)

    def control(*args):
        try:
            return subprocess.run(
                [docker_binary, "--context", _CONTEXT, *args],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                shell=False, close_fds=True, env=environment, timeout=3, check=False,
                **({"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {})
            ).returncode
        except (OSError, subprocess.TimeoutExpired):
            return None

    for attempt in range(attempts):
        if control("container", "inspect", container_name) == 0:
            control("container", "kill", container_name)
        if control("container", "rm", "--force", "--volumes", container_name) == 0:
            return True
        if attempt + 1 < attempts:
            time.sleep(0.5)
    return False


def run_watchdog(container_name, deadline_unix, docker_binary, docker_env):
    """Convert the deadline to a monotonic budget once, then reap on expiry."""
    _validate_resource(container_name, docker_binary)
    if type(deadline_unix) not in (int, float) or not math.isfinite(deadline_unix):
        raise ValueError("Invalid execution guard deadline")
    remaining = max(0.0, min(600.0, deadline_unix - time.time()))
    deadline = time.monotonic() + remaining
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(remaining, 1.0))
    return reap_container(container_name, docker_binary, docker_env)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--container", required=True)
    parser.add_argument("--deadline", type=float, required=True)
    parser.add_argument("--docker", required=True)
    args = parser.parse_args()
    try:
        success = run_watchdog(args.container, args.deadline, args.docker, os.environ)
    except Exception:
        success = False
    raise SystemExit(0 if success else 1)
