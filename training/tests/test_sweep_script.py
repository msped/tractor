"""
Tests for the standalone ceiling sweep in scripts/sweep_spancat.py.

The script is not part of the Django project — it deliberately runs without
it — so it is loaded here from its path. What is worth testing is the part
that decides what gets compared: which files count as documents, and whether
every ceiling is scored on the same held-out material.
"""

import importlib.util
import tempfile
from pathlib import Path

from django.test import SimpleTestCase

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = REPO_ROOT / "scripts" / "sweep_spancat.py"


def load_script():
    spec = importlib.util.spec_from_file_location("sweep_spancat", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sweep = load_script()


class FindDocsTests(SimpleTestCase):
    def test_finds_documents_in_a_stable_order(self):
        """
        Order has to be deterministic: the train/dev split is taken from it,
        and a split that differs between runs would make the ceilings
        incomparable.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("b.docx", "a.docx", "c.docx"):
                (root / name).touch()
            (root / "nested").mkdir()
            (root / "nested" / "d.docx").touch()

            found = sweep.find_docs([root])

        self.assertEqual(
            [p.name for p in found], ["a.docx", "b.docx", "c.docx", "d.docx"]
        )

    def test_ignores_words_lock_files(self):
        """A ~$ file is Word's lock, not a document, and will not parse."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "report.docx").touch()
            (root / "~$report.docx").touch()

            found = sweep.find_docs([root])

        self.assertEqual([p.name for p in found], ["report.docx"])

    def test_ignores_macos_appledouble_companions(self):
        """
        BSD tar packs a ._ sidecar per file, so a corpus tarred on a Mac
        arrives on a Linux box at twice the size with half of it unreadable.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "report.docx").touch()
            (root / "._report.docx").touch()

            found = sweep.find_docs([root])

        self.assertEqual([p.name for p in found], ["report.docx"])

    def test_ignores_other_file_types(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "report.docx").touch()
            (root / "report.pdf").touch()
            (root / "notes.txt").touch()

            found = sweep.find_docs([root])

        self.assertEqual([p.name for p in found], ["report.docx"])

    def test_a_missing_directory_stops_the_run(self):
        with self.assertRaises(SystemExit):
            sweep.find_docs(["/no/such/directory"])


class SplitCorpusTests(SimpleTestCase):
    def test_the_same_seed_gives_the_same_split(self):
        data = [(f"doc {i}", {"entities": []}) for i in range(20)]

        first = sweep.split_corpus(data, 0.2, seed=7)
        second = sweep.split_corpus(data, 0.2, seed=7)

        self.assertEqual(first, second)

    def test_a_different_seed_gives_a_different_split(self):
        data = [(f"doc {i}", {"entities": []}) for i in range(20)]

        _train_a, dev_a = sweep.split_corpus(data, 0.2, seed=1)
        _train_b, dev_b = sweep.split_corpus(data, 0.2, seed=2)

        self.assertNotEqual(dev_a, dev_b)

    def test_dev_share_decides_how_much_is_held_back(self):
        data = [(f"doc {i}", {"entities": []}) for i in range(20)]

        train, dev = sweep.split_corpus(data, 0.25, seed=0)

        self.assertEqual((len(train), len(dev)), (15, 5))

    def test_every_document_lands_on_exactly_one_side(self):
        data = [(f"doc {i}", {"entities": []}) for i in range(20)]

        train, dev = sweep.split_corpus(data, 0.2, seed=3)

        self.assertEqual(len(train) + len(dev), len(data))
        self.assertEqual(
            sorted(t[0] for t in train + dev), sorted(d[0] for d in data)
        )


class PeakRssTests(SimpleTestCase):
    def test_reports_a_plausible_figure_for_this_process(self):
        peak = sweep.peak_rss_mb()

        self.assertGreater(peak, 1)
        self.assertLess(peak, 1_000_000)


class WriteSummaryTests(SimpleTestCase):
    def _report(self, runs, survey=None):
        return {
            "generated_at": "2026-10-22T12:00:00+00:00",
            "host": {"platform": "Linux-x86_64", "cpus": 8},
            "documents": 120,
            "skipped_documents": 2,
            "survey": survey,
            "runs": runs,
        }

    def _run(self, ceiling, f1):
        return {
            "ceiling": ceiling,
            "status": "ok",
            "best": {
                "precision": 0.97,
                "recall": 0.91,
                "f1": f1,
                "epoch": 6,
            },
            "epochs": [{"epoch": n} for n in range(1, 8)],
            "timing": {"train_seconds": 7200},
            "peak_rss_mb": 18432,
            "corpus": {"split": 231},
        }

    def test_tabulates_each_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "summary.md"
            sweep.write_summary(path, self._report([self._run(40, 0.9414)]))
            written = path.read_text()

        self.assertIn("| 40 | 0.9700 | 0.9100 | 0.9414 | 6 | 7 |", written)
        self.assertIn("120", written)
        self.assertIn("18.0", written)  # peak RSS in GB

    def test_reports_the_coverage_survey_when_there_is_one(self):
        survey = {
            "annotations": 18561,
            "longest_span_tokens": 212,
            "unreachable": {"40": {"annotations": 223, "share": 0.012}},
        }

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "summary.md"
            sweep.write_summary(path, self._report([], survey=survey))
            written = path.read_text()

        self.assertIn("18561 annotations", written)
        self.assertIn("| 40 | 223 | 1.20% |", written)

    def test_names_the_ceilings_that_failed(self):
        """
        A ceiling that exhausts the machine's memory is a result worth
        reporting, not a reason to lose the ones that succeeded.
        """
        failed = {
            "ceiling": 128,
            "status": "failed",
            "error": "subprocess exited -9",
        }

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "summary.md"
            sweep.write_summary(
                path, self._report([self._run(40, 0.94), failed])
            )
            written = path.read_text()

        self.assertIn("## Failed", written)
        self.assertIn("ceiling 128: subprocess exited -9", written)

    def test_a_run_that_never_improved_still_tabulates(self):
        run = self._run(40, 0.0)
        run["best"] = {
            "precision": None,
            "recall": None,
            "f1": None,
            "epoch": None,
        }

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "summary.md"
            sweep.write_summary(path, self._report([run]))
            written = path.read_text()

        self.assertIn("| 40 | - | - | - | - |", written)
