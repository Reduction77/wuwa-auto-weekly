import tempfile
import unittest
from pathlib import Path
from garden.core import CycleTracker, Store, Runner, Observation


class FastControl:
    def check(self): pass
    def wait(self, seconds): pass


class FakeDriver:
    def __init__(self, observations):
        self.observations = iter(observations)
        self.actions = []
    def observe(self): return next(self.observations)
    def act(self, name): self.actions.append(name)
    def step(self, obs): self.actions.append(obs.state)


class Tests(unittest.TestCase):
    def test_cycle_requires_switch(self):
        tracker = CycleTracker()
        self.assertTrue(tracker.visit('a'))
        with self.assertRaises(RuntimeError): tracker.visit('a')
        self.assertTrue(tracker.visit('b'))
        self.assertFalse(tracker.visit('a'))

    def test_full_score_claims_and_stops_without_reward_verification(self):
        driver = FakeDriver([Observation('weekly',dict(current=6000,target=6000))])
        Runner(driver,None,FastControl(),lambda *args:None).clear('test')
        self.assertEqual(driver.actions,['claim'])

    def test_partial_enters_then_finishes_at_target(self):
        driver = FakeDriver([Observation('weekly',dict(current=3000)),
                             Observation('weekly',dict(current=6000))])
        Runner(driver,None,FastControl(),lambda *args:None).clear('test')
        self.assertEqual(driver.actions,['enter','claim'])

    def test_bad_progress_stops(self):
        driver = FakeDriver([Observation('weekly',{})])
        with self.assertRaises(RuntimeError):
            Runner(driver,None,FastControl(),lambda *args:None).clear('test')
        self.assertEqual(driver.actions,[])

    def test_binding_prevents_wrong_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            store = Store(Path(temp)/'test.db')
            store.bind('a','123456789')
            with self.assertRaises(RuntimeError): store.bind('a','987654321')
            with self.assertRaises(RuntimeError): store.bind('b','123456789')


if __name__ == '__main__': unittest.main()
