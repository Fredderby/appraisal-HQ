import unittest
from gender_detect import detect_gender

class TestDetect(unittest.TestCase):
    def test_strong_female(self):
        g,c = detect_gender("Deborah Otuo Twumasi")
        self.assertEqual(g, "female"); self.assertEqual(c, "high")
    def test_strong_male(self):
        g,c = detect_gender("Daniel Owusu Larbi")
        self.assertEqual(g, "male"); self.assertEqual(c, "high")
    def test_parens(self):
        g,c = detect_gender("Isaac Adjie ( Accounts)")
        self.assertEqual(g, "male")
    def test_unknown(self):
        g,c = detect_gender("Xyz Qqq")
        self.assertEqual(g, "unspecified")
