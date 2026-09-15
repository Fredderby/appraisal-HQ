import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from main import (
    _build_report_categories,
    _build_report_staff,
    _sort_report_rows,
    _report_summary_rows,
    REPORT_CATEGORY_LABELS,
)
from core import CATEGORIES


def _sample_staff():
    return {"id": "s1", "name": "Abc Def", "gender": "male", "gender_confidence": "high"}


def _stats(avgs=None):
    avgs = avgs or {key: None for key in CATEGORIES}
    bands = {b: 0 for b in ("Excellent", "Very Good", "Good", "Fair", "Needs Improvement")}
    cats = {}
    for key in CATEGORIES:
        avg = avgs.get(key)
        entry = {"samples": 1 if avg is not None else 0, "avg": avg, "min": avg, "max": avg,
                 "bands": dict(bands)}
        if avg is not None:
            entry["bands"]["Excellent"] = 1 if avg >= 90 else 0
        cats[key] = entry
    return {
        "staff_name": "Abc Def",
        "count": sum(1 for a in avgs.values() if a is not None) or 0,
        "devices": 2,
        "first_appraisal": None,
        "last_appraisal": None,
        "categories": cats,
        "strengths": ["Good team player"],
        "improvements": ["Keep deadlines"],
    }


class TestBuildReportCategories(unittest.TestCase):
    def test_order_and_labels_match_categorories(self):
        stats = _stats({"christian_conduct": 95.0, "overall": 85.0})
        rows = _build_report_categories(stats)
        self.assertEqual([r["key"] for r in rows], list(CATEGORIES))
        for r in rows:
            self.assertEqual(r["label"], REPORT_CATEGORY_LABELS[r["key"]])

    def test_band_and_pct_mapping(self):
        stats = _stats({
            "christian_conduct": 95.0,
            "job_performance": 85.0,
            "reliability": 75.0,
            "teamwork": 65.0,
            "communication": 55.0,
            "initiative": None,
            "adaptability": None,
            "overall": 88.0,
        })
        rows = {r["key"]: r for r in _build_report_categories(stats)}
        self.assertEqual(rows["christian_conduct"]["band"], "Excellent")
        self.assertEqual(rows["christian_conduct"]["pct"], 95)
        self.assertEqual(rows["job_performance"]["band"], "Very Good")
        self.assertEqual(rows["reliability"]["band"], "Good")
        self.assertEqual(rows["teamwork"]["band"], "Fair")
        self.assertEqual(rows["communication"]["band"], "Needs Improvement")
        self.assertIsNone(rows["initiative"]["avg"])
        self.assertEqual(rows["initiative"]["pct"], 0)
        self.assertEqual(rows["initiative"]["band"], None)
        self.assertEqual(rows["overall"]["band"], "Very Good")

    def test_empty_stats_has_data_false(self):
        stats = _stats()
        rows = _build_report_categories(stats)
        self.assertEqual(len(rows), len(CATEGORIES))
        for r in rows:
            self.assertIsNone(r["avg"])


class TestBuildReportStaff(unittest.TestCase):
    def test_with_data(self):
        stats = _stats({"christian_conduct": 90.0, "overall": 82.0})
        r = _build_report_staff(_sample_staff(), stats)
        self.assertTrue(r["has_data"])
        self.assertEqual(r["name"], "Abc Def")
        self.assertEqual(r["gender"], "male")
        self.assertEqual(r["count"], 2)
        self.assertEqual(r["devices"], 2)
        self.assertEqual(r["overall"]["avg"], 82.0)
        self.assertEqual(r["overall"]["band"], "Very Good")
        self.assertEqual(r["strengths"], ["Good team player"])
        self.assertEqual(r["improvements"], ["Keep deadlines"])

    def test_no_data(self):
        r = _build_report_staff(_sample_staff(), _stats())
        self.assertFalse(r["has_data"])
        self.assertEqual(r["count"], 0)
        self.assertIsNone(r["overall"])


class TestSortReportRows(unittest.TestCase):
    def test_sorts_by_avg_desc_then_name(self):
        a = _build_report_staff({"id": "a", "name": "Alice", "gender": "female", "gender_confidence": None},
                                _stats({"overall": 80.0}))
        b = _build_report_staff({"id": "b", "name": "Bob", "gender": "male", "gender_confidence": None},
                                _stats({"overall": 95.0}))
        c = _build_report_staff({"id": "c", "name": "Charlie", "gender": "male", "gender_confidence": None},
                                _stats({"overall": 95.0}))
        d = _build_report_staff({"id": "d", "name": "Dana", "gender": "female", "gender_confidence": None},
                                _stats())
        rows = _sort_report_rows([a, b, c, d])
        self.assertEqual([r["name"] for r in rows], ["Bob", "Charlie", "Alice", "Dana"])

    def test_no_data_rows_last(self):
        d = _build_report_staff({"id": "d", "name": "Dana", "gender": "female", "gender_confidence": None},
                                _stats())
        a = _build_report_staff({"id": "a", "name": "Alice", "gender": "female", "gender_confidence": None},
                                _stats({"overall": 70.0}))
        rows = _sort_report_rows([d, a])
        self.assertEqual([r["name"] for r in rows], ["Alice", "Dana"])


class TestReportSummaryRows(unittest.TestCase):
    def test_ranks_and_no_data_placeholder(self):
        bob = _build_report_staff({"id": "b", "name": "Bob", "gender": "male", "gender_confidence": None},
                                  _stats({"overall": 95.0}))
        dana = _build_report_staff({"id": "d", "name": "Dana", "gender": "female", "gender_confidence": None},
                                   _stats())
        rows = _report_summary_rows([bob, dana])
        self.assertEqual(rows[0]["rank"], 1)
        self.assertEqual(rows[0]["name"], "Bob")
        self.assertEqual(rows[0]["avg"], 95.0)
        self.assertEqual(rows[0]["band"], "Excellent")
        self.assertEqual(rows[1]["rank"], 2)
        self.assertEqual(rows[1]["avg"], None)
        self.assertEqual(rows[1]["band"], None)


if __name__ == "__main__":
    unittest.main()