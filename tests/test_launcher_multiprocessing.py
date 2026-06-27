from pathlib import Path
import ast
import unittest


class LauncherMultiprocessingTests(unittest.TestCase):
    def test_launcher_calls_freeze_support_before_gui_main(self):
        launcher = Path(__file__).resolve().parents[1] / "single_page_launcher.py"
        tree = ast.parse(launcher.read_text(encoding="utf-8"))

        imports_multiprocessing = any(
            isinstance(node, ast.Import) and any(alias.name == "multiprocessing" for alias in node.names)
            for node in tree.body
        )
        self.assertTrue(imports_multiprocessing)

        main_guard = next(
            (
                node for node in tree.body
                if isinstance(node, ast.If)
                and isinstance(node.test, ast.Compare)
                and isinstance(node.test.left, ast.Name)
                and node.test.left.id == "__name__"
            ),
            None,
        )
        self.assertIsNotNone(main_guard)

        call_names = []
        for node in main_guard.body:
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                func = node.value.func
                if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                    call_names.append(f"{func.value.id}.{func.attr}")
                elif isinstance(func, ast.Name):
                    call_names.append(func.id)

        self.assertIn("multiprocessing.freeze_support", call_names)
        self.assertIn("main", call_names)
        self.assertLess(
            call_names.index("multiprocessing.freeze_support"),
            call_names.index("main"),
        )


if __name__ == "__main__":
    unittest.main()
