"""Trusted watchdog behavior; subprocess and Docker are always mocked."""
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest
from unittest.mock import Mock, patch

from backend.execution.watchdog import reap_container, run_watchdog, start_watchdog


NAME = "ai-tutor-m1-" + "a" * 32


class WatchdogTests(unittest.TestCase):
    def test_guard_is_independent_and_receives_only_trusted_resource_identity(self):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "must-not-reach-guard"}), \
                patch("backend.execution.watchdog.subprocess.Popen") as launch:
            guard = start_watchdog(NAME, time.time() + 4, sys.executable, os.environ)
        self.assertIs(guard.process, launch.return_value)
        args = launch.call_args.args[0]
        options = launch.call_args.kwargs
        self.assertEqual(args[:3], [sys.executable, "-I", "-B"])
        self.assertTrue(Path(args[3]).is_absolute())
        self.assertIn(NAME, args)
        self.assertNotIn("DEEPSEEK_API_KEY", options["env"])
        self.assertIs(options["stdout"], subprocess.DEVNULL)
        self.assertIs(options["stderr"], subprocess.DEVNULL)
        self.assertIs(options["stdin"], subprocess.DEVNULL)
        self.assertFalse(options["shell"])

    def test_invalid_resource_or_deadline_cannot_launch_a_cleanup_process(self):
        with patch("backend.execution.watchdog.subprocess.Popen") as launch:
            for name in ("other-container", NAME + "\n", NAME + " --all", "ai-tutor-m1-"):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    start_watchdog(name, time.time() + 4, sys.executable, {})
            for deadline in (True, float("nan"), float("inf"), time.time() - 1, time.time() + 900):
                with self.subTest(deadline=deadline), self.assertRaises(ValueError):
                    start_watchdog(NAME, deadline, sys.executable, {})
            with self.assertRaises(ValueError):
                start_watchdog(NAME, time.time() + 4, "docker", {})
        launch.assert_not_called()

    def test_deadline_reaps_exact_container_and_discards_all_docker_output(self):
        with patch("backend.execution.watchdog.subprocess.run",
                   return_value=Mock(returncode=0)) as docker:
            self.assertTrue(reap_container(NAME, sys.executable, {"DEEPSEEK_API_KEY": "hidden"}))
        commands = [call.args[0] for call in docker.call_args_list]
        self.assertEqual(commands, [
            [sys.executable, "--context", "desktop-linux", "container", "inspect", NAME],
            [sys.executable, "--context", "desktop-linux", "container", "kill", NAME],
            [sys.executable, "--context", "desktop-linux", "container", "rm", "--force", "--volumes", NAME],
        ])
        for call in docker.call_args_list:
            self.assertIs(call.kwargs["stdout"], subprocess.DEVNULL)
            self.assertIs(call.kwargs["stderr"], subprocess.DEVNULL)
            self.assertLessEqual(call.kwargs["timeout"], 3)
            self.assertNotIn("DEEPSEEK_API_KEY", call.kwargs["env"])

    def test_engine_failure_has_bounded_retries_and_never_confirms_cleanup(self):
        with patch("backend.execution.watchdog.subprocess.run", side_effect=OSError("private path")) as docker, \
                patch("backend.execution.watchdog.time.sleep") as sleep:
            self.assertFalse(reap_container(NAME, sys.executable, {}))
        self.assertEqual(docker.call_count, 6)
        self.assertEqual(sleep.call_count, 2)

    def test_timed_out_control_command_can_retry_without_exposing_error(self):
        outcomes = [subprocess.TimeoutExpired("private command", 3), Mock(returncode=1),
                    Mock(returncode=0), Mock(returncode=0), Mock(returncode=0)]
        with patch("backend.execution.watchdog.subprocess.run", side_effect=outcomes) as docker, \
                patch("backend.execution.watchdog.time.sleep"):
            self.assertTrue(reap_container(NAME, sys.executable, {}))
        self.assertEqual(docker.call_count, 5)

    def test_wait_uses_a_monotonic_budget_after_unix_deadline_conversion(self):
        with patch("backend.execution.watchdog.time.time", return_value=100), \
                patch("backend.execution.watchdog.time.monotonic", side_effect=[50, 51, 54]), \
                patch("backend.execution.watchdog.time.sleep") as sleep, \
                patch("backend.execution.watchdog.subprocess.run", return_value=Mock(returncode=0)) as docker:
            self.assertTrue(run_watchdog(NAME, 104, sys.executable, {}))
        sleep.assert_called_once_with(1.0)
        self.assertEqual(docker.call_count, 3)

    def test_normal_cleanup_stops_guard_and_escalates_if_it_does_not_exit(self):
        process = Mock()
        process.poll.return_value = None
        process.wait.side_effect = [subprocess.TimeoutExpired("guard", 2), 0]
        with patch("backend.execution.watchdog.subprocess.Popen", return_value=process):
            guard = start_watchdog(NAME, time.time() + 4, sys.executable, {})
        guard.stop()
        process.terminate.assert_called_once()
        process.kill.assert_called_once()
        self.assertEqual(process.wait.call_count, 2)


if __name__ == "__main__":
    unittest.main()
