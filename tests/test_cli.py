"""
CLI regression tests — ensure main.py stays compatible with the shared scheduler.
"""

import os
import sys
import unittest
from io import StringIO
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import main


class CLITests(unittest.TestCase):
    def test_main_runs_without_generator_len_error(self):
        """main.py must consume the scheduler generator before counting results."""
        with patch("sys.stdout", new_callable=StringIO):
            try:
                main.main()
            except SystemExit:
                pass
            except TypeError as exc:
                if "generator" in str(exc) and "len()" in str(exc):
                    self.fail("CLI still treats scheduler.generate() as a list")
                raise


if __name__ == "__main__":
    unittest.main()
