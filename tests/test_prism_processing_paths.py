from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
import os
import tempfile
import unittest
from unittest import mock

from PIL import Image

import modules.mod_prism as mod_prism


@contextmanager
def changed_cwd(path):
    previous = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


class DummyFrame:
    x = 0
    y = 0


class DummyImg:
    images = [DummyFrame()]

    def build(self, frame):
        return Image.new("RGBA", (2, 2), (255, 0, 0, 255))


class DummyFile:
    name = "sprite.img"
    data = b"old-img"

    def set_data(self, data):
        self.data = data


class DummyNpk:
    def __init__(self):
        self.files = [DummyFile()]

    @classmethod
    def open(cls, handle):
        return cls()

    def load_all(self):
        pass

    def save(self, handle):
        handle.write(b"saved-npk")


def make_task(root):
    npk_path = root / "input.npk"
    out_dir = root / "Output_MOD"
    patcher = root / "NpkPatcher.exe"
    npk_path.write_bytes(b"dummy")
    patcher.write_bytes(b"dummy")
    out_dir.mkdir()
    return (
        str(npk_path), str(out_dir), str(patcher),
        "none", None, 0,
        "none", None, 0, 1.0, (255, 255, 255), (255, 255, 255),
        {}, False,
    )


class PrismProcessingPathTests(unittest.TestCase):
    def test_safe_cleanup_refuses_unmarked_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp) / "allowed"
            parent.mkdir()
            protected = parent / "dnf_prism_keep"
            protected.mkdir()
            (protected / "important.txt").write_text("keep", encoding="utf-8")

            with mock.patch.object(mod_prism, "_ascii_temp_parent_candidates", return_value=[str(parent)]):
                removed = mod_prism._safe_remove_temp_root(str(protected))

            self.assertFalse(removed)
            self.assertTrue((protected / "important.txt").exists())

    def test_safe_cleanup_refuses_directory_outside_allowed_temp_parent(self):
        with tempfile.TemporaryDirectory() as tmp:
            allowed = Path(tmp) / "allowed"
            allowed.mkdir()
            outside = Path(tmp) / "outside" / "dnf_prism_keep"
            outside.mkdir(parents=True)
            (outside / mod_prism.TEMP_MARKER_FILE).write_text("owned", encoding="ascii")
            (outside / "important.txt").write_text("keep", encoding="utf-8")

            with mock.patch.object(mod_prism, "_ascii_temp_parent_candidates", return_value=[str(allowed)]):
                removed = mod_prism._safe_remove_temp_root(str(outside))

            self.assertFalse(removed)
            self.assertTrue((outside / "important.txt").exists())

    def test_safe_cleanup_removes_marked_directory_created_by_prism(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp) / "allowed"
            parent.mkdir()

            with mock.patch.object(mod_prism, "_get_ascii_temp_parent", return_value=str(parent)), \
                 mock.patch.object(mod_prism, "_ascii_temp_parent_candidates", return_value=[str(parent)]):
                temp_root = Path(mod_prism._make_ascii_temp_root(1234))
                (temp_root / "data.txt").write_text("temporary", encoding="utf-8")
                removed = mod_prism._safe_remove_temp_root(str(temp_root))

            self.assertTrue(removed)
            self.assertFalse(temp_root.exists())

    def test_patcher_runs_in_ascii_temp_dir_when_app_cwd_has_chinese(self):
        with tempfile.TemporaryDirectory() as tmp:
            chinese_root = Path(tmp) / "中文工具箱"
            chinese_root.mkdir()
            task = make_task(chinese_root)
            observed = {}

            def fake_run(args, cwd, capture_output, startupinfo):
                observed["cwd"] = cwd
                csv_text = Path(cwd, "data.csv").read_text(encoding="gbk")
                observed["csv_text"] = csv_text
                Path(cwd, "new.img").write_bytes(b"new-img")
                return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

            with changed_cwd(chinese_root), \
                 mock.patch.object(mod_prism, "NPK", DummyNpk, create=True), \
                 mock.patch.object(mod_prism, "IMGFactory", SimpleNamespace(open=lambda data: DummyImg()), create=True), \
                 mock.patch.object(mod_prism, "ImageProcessor", SimpleNamespace(process=lambda image, *args, **kwargs: image)), \
                 mock.patch.object(mod_prism.subprocess, "run", side_effect=fake_run):
                success, msg = mod_prism.process_one_npk_task(task)

            self.assertTrue(success, msg)
            observed["cwd"].encode("ascii")
            first_image_path = observed["csv_text"].split(",", 1)[0]
            first_image_path.encode("ascii")
            self.assertFalse(Path(observed["cwd"]).exists())

    def test_patcher_failure_is_reported_instead_of_succeeding_with_zero_modifications(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task = make_task(root)

            def fake_run(args, cwd, capture_output, startupinfo):
                return SimpleNamespace(returncode=7, stdout=b"", stderr=b"patcher failed")

            with changed_cwd(root), \
                 mock.patch.object(mod_prism, "NPK", DummyNpk, create=True), \
                 mock.patch.object(mod_prism, "IMGFactory", SimpleNamespace(open=lambda data: DummyImg()), create=True), \
                 mock.patch.object(mod_prism, "ImageProcessor", SimpleNamespace(process=lambda image, *args, **kwargs: image)), \
                 mock.patch.object(mod_prism.subprocess, "run", side_effect=fake_run):
                success, msg = mod_prism.process_one_npk_task(task)

            self.assertFalse(success)
            self.assertIn("NpkPatcher", msg)


if __name__ == "__main__":
    unittest.main()
