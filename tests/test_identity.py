import unittest
from garden.identity import read_uid


class IdentityTests(unittest.TestCase):
    def test_mainland_feature_code(self):
        self.assertEqual(read_uid([('特征码: 100123456',.99,(2400,1420))],2560,1440),'100123456')

    def test_ordinary_version_number_rejected(self):
        self.assertIsNone(read_uid([('版本号: 100123456',.99,(2400,1420))],2560,1440))
    def test_explicit_uid(self):
        self.assertEqual(read_uid([('UID: 123456789',.99,(1900,1060))],1920,1080),'123456789')

    def test_unlabelled_digits_are_not_identity(self):
        self.assertIsNone(read_uid([('123456789',.99,(1900,1060))],1920,1080))

    def test_wrong_region_rejected(self):
        self.assertIsNone(read_uid([('UID 123456789',.99,(600,200))],1920,1080))

    def test_conflicting_identity_rejected(self):
        self.assertIsNone(read_uid([('UID 123456789',.99,(1900,1060)),
                                    ('UID 987654321',.99,(1850,1050))],1920,1080))
