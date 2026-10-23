from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from services import record_service


class RecordServiceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "records.json"
        # Safety net even before environment-path support exists: never touch real data.
        self.fallback = patch.object(record_service, "FILE_PATH", Path(self.directory.name) / "fallback.json")
        self.fallback.start()
        self.addCleanup(self.fallback.stop)
        self.environment = patch.dict(os.environ, {"AI_TUTOR_RECORDS_PATH": str(self.path)})
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def valid_record(self, **extra):
        return {"question": "sample", "error_type": "index", "knowledge": "list",
                "hint_level": 1, **extra}

    def test_dynamic_path_appends_without_rejecting_or_changing_old_record(self):
        old = {"question": "legacy"}
        self.path.write_text(json.dumps([old]), encoding="utf-8")
        record_service.save_record(self.valid_record(record_id="r1"))
        self.assertEqual(record_service.load_records(), [old, self.valid_record(record_id="r1")])
        other = Path(self.directory.name) / "other.json"
        with patch.dict(os.environ, {"AI_TUTOR_RECORDS_PATH": str(other)}):
            self.assertEqual(record_service.load_records(), [])

    def test_update_hints_changes_only_the_matching_record_and_preserves_extensions(self):
        records = [{"question": "legacy"}, self.valid_record(record_id="first", note="keep"),
                   self.valid_record(record_id="second")]
        self.path.write_text(json.dumps(records), encoding="utf-8")
        self.assertTrue(record_service.update_record("first", {"hint_level": 2, "hints_used": [1, 2]}))
        expected = [records[0], {**records[1], "hint_level": 2, "hints_used": [1, 2]}, records[2]]
        self.assertEqual(record_service.load_records(), expected)
        before = self.path.read_bytes()
        self.assertFalse(record_service.update_record("missing", {"hint_level": 2}))
        self.assertEqual(self.path.read_bytes(), before)

    def test_corrupt_file_and_non_list_root_are_not_overwritten_by_save_or_update(self):
        for content in ("{broken", '{"records": []}'):
            with self.subTest(content=content):
                self.path.write_text(content, encoding="utf-8")
                before = self.path.read_bytes()
                with self.assertRaises(ValueError):
                    record_service.save_record(self.valid_record())
                with self.assertRaises(ValueError):
                    record_service.update_record("r1", {"hint_level": 2})
                self.assertEqual(self.path.read_bytes(), before)

    def test_failed_validation_serialization_or_replace_preserves_formal_target(self):
        record_service.save_record(self.valid_record(record_id="r1"))
        before = self.path.read_bytes()
        for invalid in ({"hint_level": True}, {"question": None}, {"knowledge": " "}):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                record_service.update_record("r1", invalid)
            self.assertEqual(self.path.read_bytes(), before)
        with self.assertRaises(TypeError):
            record_service.save_record(self.valid_record(extra=object()))
        self.assertEqual(self.path.read_bytes(), before)
        with patch("services.record_service.os.replace", side_effect=OSError("blocked")):
            with self.assertRaises(OSError):
                record_service.update_record("r1", {"hint_level": 2})
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(self.path.parent.glob(".records-*.tmp")), [])

    def test_missing_and_duplicate_record_ids_never_update_arbitrary_legacy_entries(self):
        self.path.write_text(json.dumps([None, {"question": "legacy"}, self.valid_record(record_id="same"),
                                        self.valid_record(record_id="same")]), encoding="utf-8")
        before = self.path.read_bytes()
        with self.assertRaises(ValueError):
            record_service.update_record("same", {"hint_level": 2})
        with self.assertRaises(ValueError):
            record_service.update_record("same", {"record_id": "other"})
        with self.assertRaises(ValueError):
            record_service.update_record(None, {"hint_level": 2})
        self.assertFalse(record_service.update_record("absent", {"hint_level": 2}))
        self.assertEqual(self.path.read_bytes(), before)

    def test_concurrent_saves_preserve_all_diagnoses_and_file_path_patch_remains_supported(self):
        with ThreadPoolExecutor(max_workers=6) as executor:
            list(executor.map(lambda index: record_service.save_record(self.valid_record(record_id=str(index))), range(30)))
        records = record_service.load_records()
        self.assertEqual(len(records), 30)
        self.assertEqual({record["record_id"] for record in records}, {str(index) for index in range(30)})
        with patch.dict(os.environ, {"AI_TUTOR_RECORDS_PATH": ""}):
            record_service.save_record(self.valid_record(record_id="fallback"))
            self.assertEqual(record_service.load_records(), [self.valid_record(record_id="fallback")])

    def test_transient_replace_permission_error_retries_but_persistent_error_preserves_data(self):
        record_service.save_record(self.valid_record(record_id="r1"))
        replace = os.replace
        attempts = []
        def temporarily_locked(source, target):
            attempts.append(target)
            if len(attempts) < 3:
                raise PermissionError("file temporarily busy")
            return replace(source, target)
        with patch("services.record_service.os.replace", side_effect=temporarily_locked):
            self.assertTrue(record_service.update_record("r1", {"hint_level": 2}))
        self.assertEqual(record_service.load_records()[0]["hint_level"], 2)
        self.assertEqual(len(attempts), 3)
        before = self.path.read_bytes()
        with patch("services.record_service.os.replace", side_effect=PermissionError("still busy")):
            with self.assertRaises(PermissionError):
                record_service.update_record("r1", {"hint_level": 3})
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(self.path.parent.glob(".records-*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
