import unittest
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

class ExamDate(unittest.TestCase):

    def setUp(self):
        # TODO: Initialize test data
        pass

    def test_initialization(self):
        # TODO: Write a basic initialization test
        self.assertTrue(True, "Test not yet implemented")

if __name__ == '__main__':
    unittest.main()
