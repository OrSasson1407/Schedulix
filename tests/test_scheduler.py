import unittest
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.scheduler.Scheduler import Scheduler as TargetScheduler

class Scheduler(unittest.TestCase):

    def test_abstract_class_instantiation(self):
        # Should raise TypeError because generate() is abstract
        with self.assertRaises(TypeError):
            TargetScheduler()

    def test_concrete_class_implementation(self):
        class MockScheduler(TargetScheduler):
            def generate(self, courses, exam_periods):
                return ["Mock_Schedule"]

        scheduler = MockScheduler()
        self.assertEqual(scheduler.generate([], []), ["Mock_Schedule"])

if __name__ == '__main__':
    unittest.main()
