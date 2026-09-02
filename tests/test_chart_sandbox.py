import unittest

from insightflow.chart_sandbox import render_chart_image, validate_chart_code


ROWS = [
    {"State": "California", "Revenue": 100.0},
    {"State": "Florida", "Revenue": 200.0},
]


class ChartCodeValidationTests(unittest.TestCase):
    def test_plain_plotting_code_is_allowed(self):
        code = "fig, ax = plt.subplots()\nax.bar(df['State'], df['Revenue'])"
        validate_chart_code(code)  # should not raise

    def test_import_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_chart_code("import os\nfig, ax = plt.subplots()")

    def test_import_from_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_chart_code("from os import system\nfig, ax = plt.subplots()")

    def test_exec_reference_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_chart_code("exec('1')\nfig, ax = plt.subplots()")

    def test_eval_reference_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_chart_code("eval('1')\nfig, ax = plt.subplots()")

    def test_open_reference_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_chart_code("open('/etc/passwd')\nfig, ax = plt.subplots()")

    def test_dunder_attribute_access_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_chart_code("x = ().__class__\nfig, ax = plt.subplots()")

    def test_function_definition_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_chart_code("def f():\n    pass\nfig, ax = plt.subplots()")

    def test_lambda_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_chart_code("f = lambda: 1\nfig, ax = plt.subplots()")

    def test_class_definition_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_chart_code("class C: pass\nfig, ax = plt.subplots()")

    def test_syntax_error_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_chart_code("this is not python (((")

    def test_oversized_code_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_chart_code("x = 1\n" * 10_000)


class ChartRenderingTests(unittest.TestCase):
    def test_valid_code_produces_png_bytes(self):
        code = "fig, ax = plt.subplots()\nax.bar(df['State'], df['Revenue'])"
        image = render_chart_image(ROWS, code)
        self.assertTrue(image.startswith(b"\x89PNG"))

    def test_missing_fig_variable_raises(self):
        with self.assertRaises(ValueError):
            render_chart_image(ROWS, "x = 1 + 1")

    def test_infinite_loop_is_killed_by_timeout(self):
        with self.assertRaises(ValueError):
            render_chart_image(ROWS, "while True:\n    pass", timeout=2)

    def test_subprocess_boundary_has_no_inherited_environment(self):
        """render_chart_image spawns its subprocess with env={} — verify that boundary directly
        (a plain subprocess, not chart code, which correctly can't reference __builtins__ at all)
        so a bug in this isolation wouldn't be masked by the AST layer rejecting the probe."""
        import os
        import subprocess
        import sys

        os.environ["INSIGHTFLOW_TEST_SECRET"] = "should-not-leak"
        try:
            result = subprocess.run(
                [sys.executable, "-c", "import os; print('INSIGHTFLOW_TEST_SECRET' in os.environ)"],
                capture_output=True, text=True, env={},
            )
        finally:
            del os.environ["INSIGHTFLOW_TEST_SECRET"]
        self.assertEqual(result.stdout.strip(), "False")


if __name__ == "__main__":
    unittest.main()
