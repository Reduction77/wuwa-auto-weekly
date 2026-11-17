import main
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from garden.vision import VisionDriver
from garden.weekly import WeeklyView


class EntryTests(unittest.TestCase):
    def driver(self, current):
        driver = VisionDriver.__new__(VisionDriver)
        driver.collect_weekly_entry = Mock()
        driver.weekly_view = WeeklyView(page='weekly', current=current, target=6000)
        driver.act = Mock()
        driver.evidence = Mock()
        return driver

    def test_full_week_never_enters(self):
        driver = self.driver(6000)
        self.assertIn('积分已满', driver.probe_garden_entry())
        driver.act.assert_called_once_with('claim')

    def test_unreadable_progress_never_clicks(self):
        driver = self.driver(None)
        with self.assertRaisesRegex(RuntimeError, '游历值未确认'):
            driver.probe_garden_entry()
        driver.act.assert_not_called()

    def test_input_failure_is_not_retried(self):
        driver = self.driver(0)
        driver.frame = Mock()
        driver.report = Mock()
        driver.act.side_effect = RuntimeError('input denied')
        with tempfile.TemporaryDirectory() as folder:
            driver.evidence_dir = Path(folder)
            with self.assertRaisesRegex(RuntimeError, 'input denied'):
                driver.probe_garden_entry()
        driver.act.assert_called_once_with('enter')
