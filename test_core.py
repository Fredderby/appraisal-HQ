import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from core import (
    SCORE_MIDPOINTS,
    CATEGORIES,
    score_midpoint,
    rating_band,
    normalize_name,
    device_fingerprint,
    compute_staff_stats,
)


class TestScoreMidpoint(unittest.TestCase):
    def test_maps_band_to_midpoint(self):
        self.assertEqual(score_midpoint("90-100"), 95.0)
        self.assertEqual(score_midpoint("80-89"), 85.0)
        self.assertEqual(score_midpoint("70-79"), 75.0)
        self.assertEqual(score_midpoint("60-69"), 65.0)
        self.assertEqual(score_midpoint("below-60"), 55.0)

    def test_unknown_band_returns_none(self):
        self.assertIsNone(score_midpoint("garbage"))
        self.assertIsNone(score_midpoint(""))

    def test_all_categories_have_midpoints(self):
        for value in SCORE_MIDPOINTS:
            self.assertIsNotNone(SCORE_MIDPOINTS[value])


class TestRatingBand(unittest.TestCase):
    def test_band_boundaries(self):
        self.assertEqual(rating_band(95), "Excellent")
        self.assertEqual(rating_band(90), "Excellent")
        self.assertEqual(rating_band(85), "Very Good")
        self.assertEqual(rating_band(80), "Very Good")
        self.assertEqual(rating_band(75), "Good")
        self.assertEqual(rating_band(70), "Good")
        self.assertEqual(rating_band(65), "Fair")
        self.assertEqual(rating_band(60), "Fair")
        self.assertEqual(rating_band(55), "Needs Improvement")

    def test_none_rating_returns_needs_improvement(self):
        self.assertEqual(rating_band(None), "Needs Improvement")


class TestNormalizeName(unittest.TestCase):
    def test_title_cases_and_collapses_whitespace(self):
        self.assertEqual(
            normalize_name("  EVANS amanor  acheampong "),
            "Evans Amanor Acheampong",
        )

    def test_preserves_abbreviations(self):
        self.assertEqual(normalize_name("lawrence n.y. amenyo"), "Lawrence N.Y. Amenyo")

    def test_handles_apostrophes(self):
        self.assertEqual(normalize_name("michael adu"), "Michael Adu")


class TestDeviceFingerprint(unittest.TestCase):
    def test_deterministic_for_same_inputs(self):
        a = device_fingerprint("dev-1", "1.2.3.4", "Mozilla Firefox")
        b = device_fingerprint("dev-1", "1.2.3.4", "Mozilla Firefox")
        self.assertEqual(a, b)
        self.assertEqual(len(a), 64)

    def test_changes_when_any_input_changes(self):
        base = device_fingerprint("dev-1", "1.2.3.4", "Chrome")
        self.assertNotEqual(base, device_fingerprint("dev-2", "1.2.3.4", "Chrome"))
        self.assertNotEqual(base, device_fingerprint("dev-1", "5.6.7.8", "Chrome"))
        self.assertNotEqual(base, device_fingerprint("dev-1", "1.2.3.4", "Safari"))

    def test_user_agent_normalized_case_insensitively(self):
        self.assertEqual(
            device_fingerprint("dev-1", "1.2.3.4", "  Mozilla   FireFox "),
            device_fingerprint("dev-1", "1.2.3.4", "mozilla firefox"),
        )

    def test_missing_device_id_still_fingerprints(self):
        a = device_fingerprint("", "1.2.3.4", "Chrome")
        b = device_fingerprint(None, "1.2.3.4", "Chrome")
        self.assertEqual(a, b)
        self.assertEqual(len(a), 64)


class TestComputeStaffStats(unittest.TestCase):
    def test_empty_rows(self):
        stats = compute_staff_stats([])
        self.assertEqual(stats["count"], 0)
        self.assertEqual(stats["strengths"], [])
        self.assertEqual(stats["improvements"], [])

    def test_single_row_averages(self):
        row = {
            "staff_name": "Evans Amanor Acheampong",
            "christian_conduct": "90-100",
            "job_performance": "80-89",
            "reliability": "70-79",
            "teamwork": "60-69",
            "communication": "below-60",
            "initiative": "90-100",
            "adaptability": "80-89",
            "overall_assessment": "70-79",
            "strengths": "Very dedicated",
            "improvements": "",
            "device_fp": "fp-1",
            "device_id": "dev-1",
            "created_at": None,
        }
        stats = compute_staff_stats([row])
        self.assertEqual(stats["count"], 1)
        self.assertEqual(stats["categories"]["christian_conduct"]["avg"], 95.0)
        self.assertEqual(stats["categories"]["communication"]["avg"], 55.0)
        self.assertEqual(stats["categories"]["overall"]["avg"], 75.0)
        self.assertEqual(stats["strengths"], ["Very dedicated"])
        self.assertEqual(stats["improvements"], [])

    def test_band_counts_across_rows(self):
        rows = []
        for _ in range(2):
            rows.append(
                {
                    "staff_name": "A",
                    "christian_conduct": "90-100",
                    "job_performance": "90-100",
                    "reliability": "90-100",
                    "teamwork": "90-100",
                    "communication": "90-100",
                    "initiative": "90-100",
                    "adaptability": "90-100",
                    "overall_assessment": "90-100",
                    "strengths": "",
                    "improvements": "",
                    "device_fp": "fp-x",
                    "device_id": "dev-x",
                    "created_at": None,
                }
            )
        stats = compute_staff_stats(rows)
        self.assertEqual(stats["count"], 2)
        self.assertEqual(
            stats["categories"]["christian_conduct"]["bands"]["Excellent"], 2
        )
        self.assertEqual(
            stats["categories"]["christian_conduct"]["bands"]["Very Good"], 0
        )

    def test_distinct_device_count(self):
        rows = [
            {
                "staff_name": "A",
                "christian_conduct": "90-100",
                "job_performance": "90-100",
                "reliability": "90-100",
                "teamwork": "90-100",
                "communication": "90-100",
                "initiative": "90-100",
                "adaptability": "90-100",
                "overall_assessment": "90-100",
                "strengths": "",
                "improvements": "",
                "device_fp": "fp-1",
                "device_id": "dev-1",
                "created_at": None,
            },
            {
                "staff_name": "A",
                "christian_conduct": "90-100",
                "job_performance": "90-100",
                "reliability": "90-100",
                "teamwork": "90-100",
                "communication": "90-100",
                "initiative": "90-100",
                "adaptability": "90-100",
                "overall_assessment": "90-100",
                "strengths": "",
                "improvements": "",
                "device_fp": "fp-2",
                "device_id": "dev-2",
                "created_at": None,
            },
        ]
        stats = compute_staff_stats(rows)
        self.assertEqual(stats["devices"], 2)

    def test_categories_constant(self):
        self.assertEqual(
            CATEGORIES,
            [
                "christian_conduct",
                "job_performance",
                "reliability",
                "teamwork",
                "communication",
                "initiative",
                "adaptability",
                "overall",
            ],
        )


if __name__ == "__main__":
    unittest.main()