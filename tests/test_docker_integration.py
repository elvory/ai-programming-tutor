"""Opt-in real Docker checks. No AI, official data writes or host code execution.

Run with AI_TUTOR_DOCKER_INTEGRATION=1 only after preparing the local image.
The ordinary unittest suite skips these tests and never contacts Docker.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import textwrap
import threading
import time
import unittest
from uuid import uuid4

from fastapi.testclient import TestClient
from backend.app import create_app

from backend.execution.config import ExecutionConfig
from backend.execution.docker_runner import DockerRunner
from backend.execution.schemas import ExecutionRequest
from backend.execution.service import ExecutionRejected, ExecutionService
from backend.execution.watchdog import start_watchdog


ROOT = Path(__file__).resolve().parents[1]
ENABLED = os.environ.get("AI_TUTOR_DOCKER_INTEGRATION") == "1"


def solution(body):
    return "class Solution:\n    def twoSum(self, nums, target):\n" + textwrap.indent(body, "        ") + "\n"


@unittest.skipUnless(ENABLED, "real Docker integration is opt-in")
class DockerIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hashes = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT / "data").glob("*.json")}
        cls.config = ExecutionConfig(enabled=True, image=os.environ.get("AI_TUTOR_EXECUTION_IMAGE", "python:3.12-slim"))
        cls.docker = shutil.which("docker")
        if not cls.docker:
            raise unittest.SkipTest("Docker CLI is not installed")
        probe = DockerRunner(cls.config).availability()
        if not probe["available"]:
            raise unittest.SkipTest("required Docker Engine/image unavailable: " + probe["reason"])
        cls.initial_containers = cls.owned_containers()

    @classmethod
    def owned_containers(cls):
        result = subprocess.run([cls.docker, '--context', 'desktop-linux', 'ps', '-aq', '--filter',
                                 'label=ai-tutor.execution=m1'], capture_output=True, timeout=5, check=True)
        return set(result.stdout.split())

    @classmethod
    def tearDownClass(cls):
        actual = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in cls.hashes}
        if actual != cls.hashes:
            raise AssertionError("integration checks changed official data")

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="ai-tutor-docker-test-")
        self.addCleanup(self.directory.cleanup)
        self.runner = DockerRunner(self.config, lock_directory=self.directory.name)
        self.service = ExecutionService(config=self.config, runner=self.runner)

    def tearDown(self):
        self.assertEqual(self.owned_containers(), self.initial_containers,
                         'an execution left a container behind')

    def run_code(self, source):
        result = self.service.run(ExecutionRequest(problem_id=1, language="python", code=source))
        self.assertTrue(result.cleanup_confirmed, result.model_dump())
        self.assertNotEqual(result.status, "SYSTEM_ERROR", result.model_dump())
        self.assertFalse(result.judge["official_accepted"])
        self.assertIsNotNone(result.execution_time_ms)
        return result

    def test_correct_solution_runs_and_returns_only_public_example_success(self):
        result = self.run_code(solution("print('中文输出')\nfor i in range(len(nums)):\n    for j in range(i + 1, len(nums)):\n        if nums[i] + nums[j] == target:\n            return [j, i]"))
        self.assertEqual(result.status, "SUCCESS")
        self.assertTrue(result.judge["all_passed"])
        self.assertEqual(result.judge["scope"], "public_examples")
        self.assertIn("中文输出", result.stdout)

    def test_fastapi_to_real_docker_end_to_end(self):
        with TestClient(create_app(execution_service=self.service), base_url='http://127.0.0.1:8000',
                        client=('127.0.0.1', 50001)) as client:
            token = client.get('/api/execution/session').json()['token']
            response = client.post('/api/execution/run', headers={'X-Execution-Token': token}, json={
                'problem_id': 1, 'language': 'python', 'code': solution('return [2, 1]')})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['status'], 'SUCCESS')
        self.assertTrue(response.json()['judge']['all_passed'])

    def test_missing_image_is_system_error_without_automatic_download(self):
        config = ExecutionConfig(enabled=True, image='ai-tutor-m1-missing:' + uuid4().hex)
        runner = DockerRunner(config, lock_directory=self.directory.name)
        result = runner.run(solution('return [1, 2]'), {'nums': [4, 1, 6], 'target': 7}, str(uuid4()))
        self.assertEqual(result.status, 'SYSTEM_ERROR')
        self.assertEqual(result.error_code, 'IMAGE_UNAVAILABLE')
        self.assertTrue(result.cleanup_confirmed)

    def test_wrong_solution_executes_but_does_not_pass(self):
        result = self.run_code(solution("return [0, 0]"))
        self.assertEqual(result.status, "SUCCESS")
        self.assertFalse(result.judge["all_passed"])

    def test_syntax_error(self):
        self.assertEqual(self.run_code("class Solution syntax error").status, "COMPILE_ERROR")

    def test_runtime_error(self):
        result = self.run_code(solution("raise ValueError('synthetic error')"))
        self.assertEqual(result.status, "RUNTIME_ERROR")
        self.assertIn("synthetic error", result.stderr)

    def test_infinite_loop_is_stopped_by_external_timeout(self):
        result = self.run_code(solution("while True:\n    pass"))
        self.assertEqual(result.status, "TIME_LIMIT_EXCEEDED")
        self.assertGreaterEqual(result.execution_time_ms, 2900)
        self.assertLess(result.execution_time_ms, 8000)

    def test_stdout_and_stderr_floods_are_stopped_and_bounded(self):
        for fd in (1, 2):
            with self.subTest(fd=fd):
                result = self.run_code(solution("import os\nwhile True:\n    os.write(" + str(fd) + ", b'x' * 8192)"))
                self.assertEqual(result.status, "OUTPUT_LIMIT_EXCEEDED")
                self.assertLessEqual(len(result.stdout.encode("utf-8")), 65536)
                self.assertLessEqual(len(result.stderr.encode("utf-8")), 65536)

    def test_large_memory_allocation_hits_the_container_limit(self):
        result = self.run_code(solution("data = bytearray(512 * 1024 * 1024)\nreturn [1, 2]"))
        self.assertEqual(result.status, "MEMORY_LIMIT_EXCEEDED", result.model_dump())

    def test_nonroot_readonly_network_cpu_memory_and_pid_policy(self):
        body = """import errno, json, os, socket
from pathlib import Path
assert os.geteuid() == 65534
assert 'DEEPSEEK_API_KEY' not in os.environ
assert not Path('/var/run/docker.sock').exists()
try:
    Path('/usr/local/ai-tutor-denied').write_text('blocked')
    raise AssertionError('rootfs writable')
except OSError as error:
    assert error.errno == errno.EROFS
connection = socket.socket()
connection.settimeout(0.2)
assert connection.connect_ex(('1.1.1.1', 53)) != 0
connection.close()
memory = Path('/sys/fs/cgroup/memory.max').read_text().strip()
pids = Path('/sys/fs/cgroup/pids.max').read_text().strip()
cpu = Path('/sys/fs/cgroup/cpu.max').read_text().split()
assert int(memory) == 128 * 1024 * 1024
assert int(pids) == 64
assert int(cpu[0]) / int(cpu[1]) == 0.5
status = Path('/proc/self/status').read_text()
assert 'CapEff:\\t0000000000000000' in status
assert 'NoNewPrivs:\\t1' in status
assert 'Seccomp:\\t2' in status
Path('/tmp/isolated.txt').write_text('temporary')
print(json.dumps({'uid': os.geteuid(), 'memory': memory, 'pids': pids, 'cpu': cpu}))
return [1, 2]"""
        result = self.run_code(solution(body))
        self.assertEqual(result.status, "SUCCESS", result.model_dump())
        self.assertTrue(result.judge["all_passed"])

    def test_process_flood_hits_pid_limit_and_is_cleaned(self):
        body = """import errno, subprocess
children = []
try:
    for _ in range(100):
        children.append(subprocess.Popen(['/bin/sleep', '20']))
    raise AssertionError('PID limit not enforced')
except OSError as error:
    assert error.errno == errno.EAGAIN
    assert len(children) < 64
print('PID_LIMIT_ENFORCED')
return [1, 2]"""
        result = self.run_code(solution(body))
        self.assertEqual(result.status, "SUCCESS", result.model_dump())
        self.assertIn("PID_LIMIT_ENFORCED", result.stdout)

    def test_repeated_runs_do_not_share_tmp_files_or_environment(self):
        first = self.run_code(solution("from pathlib import Path\nPath('/tmp/isolated.txt').write_text('first')\nreturn [1, 2]"))
        self.assertEqual(first.status, "SUCCESS")
        second = self.run_code(solution("from pathlib import Path\nassert not Path('/tmp/isolated.txt').exists()\nreturn [1, 2]"))
        self.assertEqual(second.status, "SUCCESS")

    def test_background_processes_do_not_outlive_container(self):
        result = self.run_code(solution("import subprocess\nsubprocess.Popen(['/bin/sleep', '20'])\nreturn [1, 2]"))
        self.assertEqual(result.status, "SUCCESS")

    def test_concurrent_request_is_rejected_without_touching_running_job(self):
        results = []
        request = ExecutionRequest(problem_id=1, language="python", code=solution("import time\ntime.sleep(1)\nreturn [1, 2]"))
        thread = threading.Thread(target=lambda: results.append(self.service.run(request)))
        thread.start()
        try:
            # Wait for actual Docker work, not an assumed thread schedule.
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                listed = subprocess.run([self.docker, '--context', 'desktop-linux', 'ps', '-q', '--filter',
                                         'label=ai-tutor.execution=m1'], capture_output=True, timeout=3, check=True)
                if listed.stdout.strip():
                    break
                time.sleep(0.05)
            else:
                self.fail('first container did not start')
            with self.assertRaises(ExecutionRejected) as rejected:
                self.service.run(request)
            self.assertEqual(rejected.exception.status_code, 429)
            # Another service instance has a separate semaphore, but must still
            # respect the shared operating-system lock.
            other = ExecutionService(config=self.config, runner=DockerRunner(self.config, lock_directory=self.directory.name))
            with self.assertRaises(ExecutionRejected) as shared_rejection:
                other.run(request)
            self.assertEqual(shared_rejection.exception.status_code, 429)
        finally:
            thread.join(timeout=12)
        self.assertFalse(thread.is_alive())
        self.assertEqual(results[0].status, 'SUCCESS')

    def test_independent_watchdog_removes_abandoned_resource(self):
        name = 'ai-tutor-m1-' + uuid4().hex
        guard = start_watchdog(name, time.time() + 1.5, self.docker, self.runner.environment)
        try:
            # A stopped container is enough to verify ownership and independent
            # deletion; no unbounded untrusted process is launched by this test.
            subprocess.run([self.docker, '--context', 'desktop-linux', 'create', '--name', name,
                            '--network=none', '--read-only', '--user=65534:65534',
                            '--cap-drop=ALL', '--security-opt=no-new-privileges',
                            self.config.image, 'python', '-c', 'pass'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10, check=True)
            guard.process.wait(timeout=15)
            listed = subprocess.run([self.docker, '--context', 'desktop-linux', 'container', 'ls', '-a',
                                     '--filter', 'name=^/' + name + '$', '--format', '{{.ID}}'],
                                    capture_output=True, timeout=5, check=True)
            self.assertEqual(listed.stdout.strip(), b'')
            self.assertEqual(guard.process.returncode, 0)
        finally:
            subprocess.run([self.docker, '--context', 'desktop-linux', 'rm', '-f', name],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5, check=False)
            guard.stop()
