import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from core import (
    hash_password,
    verify_password,
    validate_username,
    validate_password,
    validate_site_title,
    validate_staff_name,
)


class TestPasswordHashing(unittest.TestCase):
    def test_hash_is_none_equiv_and_structured(self):
        stored = hash_password("secret123")
        parts = stored.split("$")
        self.assertEqual(parts[0], "pbkdf2")
        self.assertEqual(parts[1], "sha256")
        self.assertEqual(len(parts), 5)
        self.assertTrue(parts[3])
        self.assertTrue(parts[4])

    def test_same_password_hashes_differ_but_both_verify(self):
        a = hash_password("secret123")
        b = hash_password("secret123")
        self.assertNotEqual(a, b)
        self.assertTrue(verify_password("secret123", a))
        self.assertTrue(verify_password("secret123", b))

    def test_wrong_password_fails(self):
        stored = hash_password("secret123")
        self.assertFalse(verify_password("secret124", stored))
        self.assertFalse(verify_password("", stored))

    def test_tampered_hash_fails(self):
        stored = hash_password("secret123")
        self.assertFalse(verify_password("secret123", stored + "x"))
        self.assertFalse(verify_password("secret123", "garbage"))


class TestUsernameValidation(unittest.TestCase):
    def test_valid_usernames(self):
        self.assertTrue(validate_username("admin")[0])
        self.assertTrue(validate_username("Admin_User-1")[0])
        self.assertTrue(validate_username("Fred O")[0])

    def test_invalid_usernames(self):
        self.assertFalse(validate_username("")[0])
        self.assertFalse(validate_username("   ")[0])
        self.assertFalse(validate_username("ab")[0])
        self.assertFalse(validate_username("a" * 51)[0])
        self.assertFalse(validate_username("bad name!" )[0])


class TestPasswordValidation(unittest.TestCase):
    def test_minimum_length_enforced(self):
        self.assertFalse(validate_password("short1")[0])
        self.assertTrue(validate_password("password1")[0])

    def test_empty_rejected(self):
        self.assertFalse(validate_password("")[0])


class TestSiteTitleValidation(unittest.TestCase):
    def test_title_rules(self):
        self.assertTrue(validate_site_title("DCLM Appraisal")[0])
        self.assertFalse(validate_site_title("")[0])
        self.assertFalse(validate_site_title("  ")[0])
        self.assertFalse(validate_site_title("x" * 101)[0])


class TestStaffNameValidation(unittest.TestCase):
    def test_normalizes_and_validates(self):
        ok, name = validate_staff_name("  eVaNS   amanor ACHEAMPONG ")
        self.assertTrue(ok)
        self.assertEqual(name, "Evans Amanor Acheampong")

    def test_rejects_empty(self):
        ok, _ = validate_staff_name("   ")
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()