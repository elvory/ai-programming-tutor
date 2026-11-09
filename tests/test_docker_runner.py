"""Docker CLI boundary tests; no daemon or submitted code is executed."""
import io
import json
import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from backend.execution.config import ExecutionConfig
from backend.execution.docker_runner import DockerRunner, _ExecutionLock
from backend.execution.exceptions import ExecutionBusy


class ExecutionConfigTests(unittest.TestCase):
    def test_disabled_by_default_and_limits_are_server_owned(self):
        config = ExecutionConfig.from_env({})
        self.assertFalse(config.enabled)
        self.assertEqual((config.memory_mb, config.cpu, config.pids), (128, 0.5, 64))
        self.assertEqual((config.stdout_limit, config.stderr_limit), (65536, 65536))

    def test_invalid_limits_fail_closed(self):
        for settings in ({"cpu": 0}, {"timeout_seconds": float("nan")},
                         {"max_concurrent": 2}, {"memory_mb": -1}):
            with self.subTest(settings=settings), self.assertRaises(ValueError):
                ExecutionConfig(**settings)


IMAGE_ID = "sha256:" + "a" * 64
CONTAINER_ID = "b" * 64


class FakeProcess:
    def __init__(self, stdout=b"", stderr=b"", exit_code=0, input_callback=None):
        self.stdout = io.BytesIO(stdout)
        self.stderr = io.BytesIO(stderr)
        self.stdin = io.BytesIO()
        self.returncode = exit_code
        self.input_callback = input_callback

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        return self.returncode

    def kill(self):
        self.returncode = -9


class FakeDocker:
    def __init__(self, output=b"hello\n", exit_code=0, oom=False, create_error=False, cleanup_error=False):
        self.calls = []
        self.output = output
        self.exit_code = exit_code
        self.oom = oom
        self.create_error = create_error
        self.cleanup_error = cleanup_error

    def __call__(self, args, **options):
        self.calls.append((args, options))
        command = args[3:]
        if command[0] == "info":
            return FakeProcess(json.dumps({"os": "linux", "security": ["name=seccomp,profile=builtin"]}).encode())
        if command[:2] == ["image", "inspect"]:
            return FakeProcess((IMAGE_ID + "\n").encode())
        if command[0] == "create":
            return FakeProcess((CONTAINER_ID + "\n").encode(), exit_code=1 if self.create_error else 0)
        if command[0] == "start":
            return FakeProcess(self.output, exit_code=self.exit_code)
        if command[0] == "inspect":
            return FakeProcess(json.dumps({"Running": False, "ExitCode": self.exit_code,
                "OOMKilled": self.oom, "StartedAt": "2026-01-01T00:00:00Z"}).encode())
        if command[0] in ("rm", "kill"):
            return FakeProcess(exit_code=1 if self.cleanup_error else 0)
        if command[:2] == ["container", "ls"]:
            return FakeProcess((CONTAINER_ID if self.cleanup_error else "").encode())
        raise AssertionError("Unexpected Docker command: " + repr(command))


class DockerRunnerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="ai-tutor-runner-test-")
        self.addCleanup(self.directory.cleanup)
        self.guard = Mock()
        self.guard_patch = patch("backend.execution.docker_runner.start_watchdog", return_value=self.guard)
        self.guard_patch.start()
        self.addCleanup(self.guard_patch.stop)

    def run_fake(self, docker, config=None):
        runner = DockerRunner(config or ExecutionConfig(enabled=True), docker_path="docker", lock_directory=self.directory.name)
        with patch("backend.execution.docker_runner.subprocess.Popen", side_effect=docker):
            result = runner.run("class Solution: pass", {"nums": [4, 1, 6], "target": 7}, "test-request")
        if runner._retained_lock:
            self.addCleanup(runner._retained_lock.close)
        return runner, result

    def test_run_uses_isolated_container_and_always_removes_it(self):
        docker = FakeDocker()
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "fake-never-forward"}):
            _, result = self.run_fake(docker)
        self.assertEqual(result.status, "SUCCESS")
        self.assertEqual(result.stdout, "hello\n")
        self.assertTrue(result.cleanup_confirmed)
        create = next(args for args, _ in docker.calls if args[3] == "create")
        for required in ("--read-only", "--network=none", "--cap-drop=ALL", "--security-opt=no-new-privileges",
                         "--user=65534:65534", "--memory=128m", "--memory-swap=128m", "--cpus=0.5",
                         "--pids-limit=64", "--pull=never", "--log-driver=none"):
            self.assertIn(required, create)
        self.assertIn(IMAGE_ID, create)
        self.assertNotIn("class Solution: pass", create)
        self.assertFalse(any(arg in create for arg in ("--volume", "--mount", "--privileged")))
        for _, options in docker.calls:
            self.assertFalse(options["shell"])
            self.assertNotIn("DEEPSEEK_API_KEY", options["env"])
        self.guard.stop.assert_called_once()

    def test_output_limit_kills_and_cleans_container(self):
        docker = FakeDocker(output=b"x" * 20000)
        _, result = self.run_fake(docker, ExecutionConfig(enabled=True, stdout_limit=1024))
        self.assertEqual(result.status, "OUTPUT_LIMIT_EXCEEDED")
        self.assertLessEqual(len(result.stdout.encode()), 1024)
        self.assertTrue(result.cleanup_confirmed)
        self.assertTrue(any(args[3] == "rm" for args, _ in docker.calls))

    def test_oom_evidence_is_not_runtime_error(self):
        _, result = self.run_fake(FakeDocker(exit_code=137, oom=True))
        self.assertEqual(result.status, "MEMORY_LIMIT_EXCEEDED")

    def test_system_failure_is_sanitized_and_cleanup_attempts_name(self):
        docker = FakeDocker(create_error=True)
        _, result = self.run_fake(docker)
        self.assertEqual(result.status, "SYSTEM_ERROR")
        self.assertEqual(result.stderr, "")
        self.assertTrue(any(args[3] == "rm" for args, _ in docker.calls))

    def test_cleanup_failure_leaves_watchdog_and_blocks_further_runs(self):
        docker = FakeDocker(cleanup_error=True)
        runner, result = self.run_fake(docker)
        self.addCleanup(runner._retained_lock.close)
        self.assertEqual(result.status, "SYSTEM_ERROR")
        self.assertFalse(result.cleanup_confirmed)
        self.guard.stop.assert_not_called()
        with patch("backend.execution.docker_runner.subprocess.Popen", side_effect=AssertionError("must fail closed")):
            again = runner.run("pass", {}, "again")
        self.assertEqual(again.error_code, "CLEANUP_UNCONFIRMED")

    def test_engine_and_missing_image_fail_without_pulling_or_creating(self):
        for fault, expected in (("info", "DOCKER_UNAVAILABLE"), ("image", "IMAGE_UNAVAILABLE")):
            docker = FakeDocker()

            def fail(args, **options):
                if args[3] == fault:
                    docker.calls.append((args, options))
                    return FakeProcess(stderr=b"sensitive fake host path and secret", exit_code=1)
                return docker(args, **options)

            _, result = self.run_fake(fail)
            self.assertEqual(result.status, "SYSTEM_ERROR")
            self.assertEqual(result.error_code, expected)
            self.assertEqual(result.stderr, "")
            self.assertFalse(any(args[3] in {"create", "pull"} for args, _ in docker.calls))

    def test_timeout_stops_container_and_confirms_cleanup(self):
        docker = FakeDocker()

        def delayed(args, **options):
            process = docker(args, **options)
            if args[3] == "start":
                process.returncode = None
            return process

        _, result = self.run_fake(delayed, ExecutionConfig(enabled=True, timeout_seconds=0.05))
        self.assertEqual(result.status, "TIME_LIMIT_EXCEEDED")
        self.assertTrue(result.cleanup_confirmed)
        self.assertTrue(any(args[3] == "kill" for args, _ in docker.calls))

    def test_exit_137_without_oom_evidence_is_not_mislabeled_memory_limit(self):
        _, result = self.run_fake(FakeDocker(exit_code=137, oom=False))
        self.assertEqual(result.status, "RUNTIME_ERROR")

    def test_cross_process_lock_rejects_another_runner(self):
        lock = _ExecutionLock(self.directory.name)
        try:
            with self.assertRaises(ExecutionBusy):
                self.run_fake(FakeDocker())
        finally:
            lock.close()

    def test_previous_crash_journal_is_recovered_before_new_execution(self):
        lock = _ExecutionLock(self.directory.name)
        old_name = "ai-tutor-m1-" + "c" * 32
        lock.write(old_name)
        lock.close()
        docker = FakeDocker()
        _, result = self.run_fake(docker)
        self.assertEqual(result.status, "SUCCESS")
        commands = [args[3:] for args, _ in docker.calls]
        self.assertEqual(commands[0], ["rm", "--force", "--volumes", old_name])
        self.assertTrue(commands.index(next(args for args in commands if args[0] == "create")) > 0)

    def test_unknown_create_completion_cannot_cancel_its_future_cleanup_guard(self):
        runner, result = self.run_fake(FakeDocker(create_error=True))
        self.assertEqual(result.status, "SYSTEM_ERROR")
        self.assertFalse(result.cleanup_confirmed)
        self.guard.stop.assert_not_called()
        with self.assertRaises(ExecutionBusy):
            _ExecutionLock(self.directory.name)


if __name__ == "__main__":
    unittest.main()
