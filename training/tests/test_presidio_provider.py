import threading
from unittest.mock import MagicMock, patch

from django.test import TestCase

from ..extractors.presidio_provider import (
    PresidioEngineProvider,
    PresidioSnapshot,
    RecognizerSpec,
    _load_specs_and_fingerprint,
)
from ..models import CustomDenyListItem, CustomPattern, CustomRecognizer
from .base import NetworkBlockerMixin


def _make_recognizer(
    entity_type=CustomRecognizer.EntityType.THIRD_PARTY, **kw
):
    defaults = {"name": f"Rec {CustomRecognizer.objects.count()}"}
    defaults.update(kw)
    return CustomRecognizer.objects.create(entity_type=entity_type, **defaults)


class LoadSpecsAndFingerprintTests(NetworkBlockerMixin, TestCase):
    def test_fingerprint_stable_when_config_unchanged(self):
        rec = _make_recognizer()
        CustomPattern.objects.create(recognizer=rec, regex=r"\d{4}", score=0.8)

        fp1, _ = _load_specs_and_fingerprint()
        fp2, _ = _load_specs_and_fingerprint()

        self.assertEqual(fp1, fp2)

    def test_fingerprint_changes_on_recognizer_create_and_delete(self):
        fp_empty, _ = _load_specs_and_fingerprint()
        rec = _make_recognizer()
        CustomPattern.objects.create(recognizer=rec, regex=r"\d{4}", score=0.8)

        fp_created, _ = _load_specs_and_fingerprint()
        self.assertNotEqual(fp_empty, fp_created)

        rec.delete()
        fp_deleted, _ = _load_specs_and_fingerprint()
        self.assertEqual(fp_empty, fp_deleted)

    def test_fingerprint_changes_on_pattern_queryset_update(self):
        """An in-place regex edit via queryset.update() — no save(), no
        signal, no updated_at bump — must still change the fingerprint."""
        rec = _make_recognizer()
        CustomPattern.objects.create(recognizer=rec, regex=r"\d{4}", score=0.8)
        fp_before, _ = _load_specs_and_fingerprint()

        CustomPattern.objects.filter(recognizer=rec).update(regex=r"\d{6}")

        fp_after, _ = _load_specs_and_fingerprint()
        self.assertNotEqual(fp_before, fp_after)

    def test_fingerprint_changes_on_deny_list_bulk_create(self):
        rec = _make_recognizer()
        CustomPattern.objects.create(recognizer=rec, regex=r"\d{4}", score=0.8)
        fp_before, _ = _load_specs_and_fingerprint()

        CustomDenyListItem.objects.bulk_create(
            [CustomDenyListItem(recognizer=rec, value="SuperSecret")]
        )

        fp_after, _ = _load_specs_and_fingerprint()
        self.assertNotEqual(fp_before, fp_after)

    def test_fingerprint_changes_on_is_active_toggle(self):
        rec = _make_recognizer()
        CustomPattern.objects.create(recognizer=rec, regex=r"\d{4}", score=0.8)
        fp_active, _ = _load_specs_and_fingerprint()

        CustomRecognizer.objects.filter(pk=rec.pk).update(is_active=False)

        fp_inactive, _ = _load_specs_and_fingerprint()
        self.assertNotEqual(fp_active, fp_inactive)

    def test_specs_exclude_inactive_and_empty_recognizers(self):
        active = _make_recognizer(name="Active")
        CustomPattern.objects.create(
            recognizer=active, regex=r"\d{4}", score=0.8
        )
        inactive = _make_recognizer(name="Inactive", is_active=False)
        CustomPattern.objects.create(
            recognizer=inactive, regex=r"\d{4}", score=0.8
        )
        _make_recognizer(name="Empty")  # no patterns, no deny list

        _, specs = _load_specs_and_fingerprint()

        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[0].id_hex, active.id.hex)

    def test_spec_contents(self):
        rec = _make_recognizer(
            entity_type=CustomRecognizer.EntityType.OPERATIONAL
        )
        CustomPattern.objects.create(
            recognizer=rec, name="pat", regex=r"OP-\d{6}", score=0.9
        )
        CustomDenyListItem.objects.create(recognizer=rec, value="SuperSecret")

        _, specs = _load_specs_and_fingerprint()

        self.assertEqual(
            specs,
            (
                RecognizerSpec(
                    id_hex=rec.id.hex,
                    entity_type="OPERATIONAL",
                    patterns=(("pat", r"OP-\d{6}", 0.9),),
                    deny_list=("SuperSecret",),
                ),
            ),
        )


class PresidioEngineProviderTests(NetworkBlockerMixin, TestCase):
    def setUp(self):
        PresidioEngineProvider.reset_for_tests()

    def tearDown(self):
        PresidioEngineProvider.reset_for_tests()

    def test_get_instance_returns_singleton(self):
        self.assertIs(
            PresidioEngineProvider.get_instance(),
            PresidioEngineProvider.get_instance(),
        )

    def test_same_snapshot_while_fingerprint_unchanged(self):
        provider = PresidioEngineProvider.get_instance()
        self.assertIs(provider.acquire_snapshot(), provider.acquire_snapshot())

    def test_snapshot_swapped_when_config_changes_without_save(self):
        """bulk_create fires no signals — freshness must not depend on them."""
        provider = PresidioEngineProvider.get_instance()
        first = provider.acquire_snapshot()

        rec = _make_recognizer()
        CustomPattern.objects.bulk_create(
            [CustomPattern(recognizer=rec, regex=r"\d{4}", score=0.8)]
        )

        second = provider.acquire_snapshot()
        self.assertIsNot(first, second)
        self.assertNotEqual(first.fingerprint, second.fingerprint)

    def test_old_snapshot_unaffected_by_swap(self):
        """A snapshot handed to an in-flight document keeps its own config."""
        provider = PresidioEngineProvider.get_instance()
        first = provider.acquire_snapshot()
        original_fingerprint = first.fingerprint

        rec = _make_recognizer()
        CustomPattern.objects.create(recognizer=rec, regex=r"\d", score=0.5)
        provider.acquire_snapshot()

        self.assertEqual(first.fingerprint, original_fingerprint)
        self.assertEqual(first._specs, ())


class PresidioSnapshotUnitTests(NetworkBlockerMixin, TestCase):
    """Direct-construction tests with in-memory specs — presidio mocked."""

    def _spec(self, entity_type="THIRD_PARTY", **kw):
        defaults = {
            "id_hex": "a" * 32,
            "entity_type": entity_type,
            "patterns": (("pat", r"\d{4}", 0.8),),
            "deny_list": (),
        }
        defaults.update(kw)
        return RecognizerSpec(**defaults)

    @patch("presidio_analyzer.nlp_engine.NlpEngineProvider")
    @patch("presidio_analyzer.AnalyzerEngine")
    @patch("presidio_analyzer.PatternRecognizer")
    @patch("presidio_analyzer.Pattern")
    def test_builtin_engines_register_builtins_and_customs(
        self, mock_pattern, mock_recognizer, mock_engine, mock_provider
    ):
        mock_engine_instance = MagicMock()
        mock_engine_instance.analyze.return_value = []
        mock_engine.return_value = mock_engine_instance

        snapshot = PresidioSnapshot("fp", (self._spec(),))
        snapshot.extract_third_party("text")

        # 2 builtin UK PII recognizers + 1 custom
        self.assertEqual(
            mock_engine_instance.registry.add_recognizer.call_count, 3
        )
        mock_recognizer.assert_any_call(
            supported_entity=f"CUSTOM_{'a' * 32}",
            patterns=[mock_pattern.return_value],
            deny_list=None,
        )

    @patch("presidio_analyzer.nlp_engine.NlpEngineProvider")
    @patch("presidio_analyzer.AnalyzerEngine")
    @patch("presidio_analyzer.PatternRecognizer")
    @patch("presidio_analyzer.Pattern")
    def test_builtin_engines_share_one_nlp_engine(
        self, mock_pattern, mock_recognizer, mock_engine, mock_provider
    ):
        mock_engine.return_value.analyze.return_value = []

        snapshot = PresidioSnapshot("fp", ())
        snapshot.extract_third_party("text")
        snapshot.extract_operational("text")

        # Two AnalyzerEngines built, but only one spaCy NlpEngine created
        self.assertEqual(mock_engine.call_count, 2)
        mock_provider.assert_called_once()

    @patch("presidio_analyzer.nlp_engine.NlpEngineProvider")
    @patch("presidio_analyzer.AnalyzerEngine")
    def test_engines_cached_within_snapshot(self, mock_engine, mock_provider):
        mock_engine.return_value.analyze.return_value = []

        snapshot = PresidioSnapshot("fp", ())
        snapshot.extract_third_party("one")
        snapshot.extract_third_party("two")

        mock_engine.assert_called_once()

    def test_extract_custom_short_circuits_without_specs(self):
        snapshot = PresidioSnapshot("fp", ())
        with patch.object(snapshot, "_build_engine") as mock_build:
            self.assertEqual(snapshot.extract_custom("text"), [])
        mock_build.assert_not_called()

    @patch("presidio_analyzer.nlp_engine.NlpEngineProvider")
    @patch("presidio_analyzer.AnalyzerEngine")
    @patch("presidio_analyzer.PatternRecognizer")
    @patch("presidio_analyzer.Pattern")
    def test_extract_custom_builds_only_configured_label(
        self, mock_pattern, mock_recognizer, mock_engine, mock_provider
    ):
        mock_engine.return_value.analyze.return_value = []

        snapshot = PresidioSnapshot("fp", (self._spec("THIRD_PARTY"),))
        snapshot.extract_custom("text")

        # Only the custom THIRD_PARTY engine is built — no OPERATIONAL specs
        mock_engine.assert_called_once()

    def test_result_mapping(self):
        snapshot = PresidioSnapshot("fp", ())
        mock_engine = MagicMock()
        result = MagicMock()
        result.start = 11
        result.end = 25
        mock_engine.analyze.return_value = [result]
        snapshot._engines["third_party"] = (mock_engine, [])

        text = "Call me on 07700 900000..."
        output = snapshot.extract_third_party(text)

        self.assertEqual(
            output,
            [
                {
                    "text": text[11:25],
                    "label": "THIRD_PARTY",
                    "start_char": 11,
                    "end_char": 25,
                }
            ],
        )

    def test_single_engine_build_under_contention(self):
        snapshot = PresidioSnapshot("fp", ())
        build_count = 0
        barrier = threading.Barrier(4)

        def slow_build(key):
            nonlocal build_count
            build_count += 1
            engine = MagicMock()
            engine.analyze.return_value = []
            return engine, []

        def worker():
            barrier.wait()
            snapshot.extract_third_party("text")

        with patch.object(snapshot, "_build_engine", side_effect=slow_build):
            threads = [threading.Thread(target=worker) for _ in range(4)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        self.assertEqual(build_count, 1)


class PresidioIntegrationTests(NetworkBlockerMixin, TestCase):
    """Real Presidio + spaCy — builtin patterns, custom recognizers, and
    end-to-end freshness with no signal in the loop."""

    def setUp(self):
        PresidioEngineProvider.reset_for_tests()

    def tearDown(self):
        PresidioEngineProvider.reset_for_tests()

    def _snapshot(self):
        return PresidioEngineProvider.get_instance().acquire_snapshot()

    def test_builtin_third_party_patterns_detected(self):
        results = self._snapshot().extract_third_party(
            "Write to SW1A 1AA, NI number AB 12 34 56 C."
        )

        texts = [r["text"] for r in results]
        self.assertIn("SW1A 1AA", texts)
        self.assertIn("AB 12 34 56 C", texts)
        self.assertTrue(all(r["label"] == "THIRD_PARTY" for r in results))

    def test_builtin_operational_patterns_detected(self):
        results = self._snapshot().extract_operational(
            "Crime Ref No: 42/12345/24 attended by PC 1234."
        )

        texts = [r["text"] for r in results]
        self.assertIn("42/12345/24", texts)
        self.assertIn("PC 1234", texts)
        self.assertTrue(all(r["label"] == "OPERATIONAL" for r in results))

    def test_custom_pattern_detected_via_extract_custom(self):
        rec = _make_recognizer()
        CustomPattern.objects.create(
            recognizer=rec, regex=r"BADGE-\d{4}", score=0.9
        )

        results = self._snapshot().extract_custom(
            "Officer BADGE-1234 attended."
        )

        texts = [r["text"] for r in results]
        self.assertIn("BADGE-1234", texts)
        self.assertTrue(all(r["label"] == "THIRD_PARTY" for r in results))

    def test_custom_operational_pattern_detected_in_builtin_engine(self):
        rec = _make_recognizer(
            entity_type=CustomRecognizer.EntityType.OPERATIONAL
        )
        CustomPattern.objects.create(
            recognizer=rec, regex=r"OP-REF-\d{6}", score=0.9
        )

        results = self._snapshot().extract_operational(
            "See OP-REF-123456 for details."
        )

        texts = [r["text"] for r in results]
        self.assertIn("OP-REF-123456", texts)
        self.assertTrue(all(r["label"] == "OPERATIONAL" for r in results))

    def test_custom_deny_list_detected(self):
        rec = _make_recognizer()
        CustomDenyListItem.objects.create(recognizer=rec, value="SuperSecret")

        results = self._snapshot().extract_custom(
            "The project SuperSecret must be redacted."
        )

        texts = [r["text"] for r in results]
        self.assertIn("SuperSecret", texts)

    def test_disabled_recognizer_produces_no_match(self):
        rec = _make_recognizer(is_active=False)
        CustomPattern.objects.create(
            recognizer=rec, regex=r"BADGE-\d{4}", score=0.9
        )

        results = self._snapshot().extract_custom(
            "Officer BADGE-1234 attended."
        )

        self.assertEqual(results, [])

    def test_new_rule_detected_after_reacquire_with_no_signal(self):
        """End-to-end staleness: add a pattern via bulk_create (no signal
        fires), re-acquire, and the new rule is live."""
        first = self._snapshot()
        self.assertEqual(first.extract_custom("Officer BADGE-1234."), [])

        rec = _make_recognizer()
        CustomPattern.objects.bulk_create(
            [CustomPattern(recognizer=rec, regex=r"BADGE-\d{4}", score=0.9)]
        )

        second = self._snapshot()
        self.assertIsNot(first, second)
        texts = [
            r["text"] for r in second.extract_custom("Officer BADGE-1234.")
        ]
        self.assertIn("BADGE-1234", texts)
