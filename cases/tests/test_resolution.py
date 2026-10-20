from datetime import date
from types import SimpleNamespace

from django.test import SimpleTestCase

from cases.models import Redaction
from cases.resolution import resolve_spans

DS_NAME = "Joe Bloggs"
DS_DOB = date(1990, 1, 1)


def _case(name=DS_NAME, dob=DS_DOB):
    return SimpleNamespace(data_subject_name=name, data_subject_dob=dob)


def _span(text, start, entity_type=None, label="THIRD_PARTY"):
    return {
        "text": text,
        "label": label,
        "start_char": start,
        "end_char": start + len(text),
        "entity_type": entity_type,
    }


class ResolveSpansTests(SimpleTestCase):
    def _resolve(self, text, spans, case=None, **kwargs):
        return resolve_spans(
            spans, case or _case(), extracted_text=text, **kwargs
        )

    def test_one_resolution_per_span_in_order(self):
        text = "Joe Bloggs rang 07700 900000 about SMITH, Jane"
        spans = [
            _span("Joe Bloggs", 0, "PERSON_NAME"),
            _span("07700 900000", 16, "PHONE_NUMBER"),
            _span("SMITH, Jane", 35, "PERSON_NAME"),
        ]

        results = self._resolve(text, spans)

        self.assertEqual(len(results), len(spans))

    # ---- recognition: the case record's own entry ----

    def test_data_subject_name_is_accepted_on_sight(self):
        text = "Joe Bloggs attended."
        spans = [_span("Joe Bloggs", 0, "PERSON_NAME")]

        [result] = self._resolve(text, spans)

        self.assertEqual(
            result.redaction_type, Redaction.RedactionType.DS_INFORMATION
        )
        self.assertTrue(result.is_accepted)
        self.assertEqual(
            result.decided_by, Redaction.DecidedBy.DS_RECORD_MATCH
        )
        self.assertIn("name recorded on this case", result.rationale)

    def test_data_subject_dob_is_accepted_on_sight(self):
        text = "DOB: 01/01/1990"
        spans = [_span("01/01/1990", 5, "date of birth")]

        [result] = self._resolve(text, spans)

        self.assertTrue(result.is_accepted)
        self.assertIn("date of birth recorded on this case", result.rationale)

    # ---- inference: a detail attributed to the data subject ----

    def test_detail_in_the_data_subjects_block_is_proposed_pending(self):
        text = "Joe Bloggs\t07700 900000"
        spans = [
            _span("Joe Bloggs", 0, "PERSON_NAME"),
            _span("07700 900000", 11, "PHONE_NUMBER"),
        ]

        _, phone = self._resolve(text, spans)

        self.assertEqual(
            phone.redaction_type, Redaction.RedactionType.DS_INFORMATION
        )
        self.assertFalse(phone.is_accepted)
        self.assertIsNone(phone.decided_by)

    def test_the_rationale_names_the_person_and_where_it_was_read(self):
        text = "Joe Bloggs\t07700 900000"
        spans = [
            _span("Joe Bloggs", 0, "PERSON_NAME"),
            _span("07700 900000", 11, "PHONE_NUMBER"),
        ]

        _, phone = self._resolve(text, spans)

        self.assertIn("Joe Bloggs", phone.rationale)
        self.assertIn("line", phone.rationale)

    def test_a_table_row_is_named_as_such_in_the_rationale(self):
        structure = [{"type": "table", "table_id": 0, "start": 0, "end": 23}]
        tables = [
            {
                "id": 0,
                "cells": [
                    {
                        "row": 0,
                        "col": 0,
                        "text": "Joe Bloggs",
                        "start": 0,
                        "end": 10,
                        "isMergedContinuation": False,
                    },
                    {
                        "row": 0,
                        "col": 1,
                        "text": "07700 900000",
                        "start": 11,
                        "end": 23,
                        "isMergedContinuation": False,
                    },
                ],
            }
        ]
        spans = [
            _span("Joe Bloggs", 0, "PERSON_NAME"),
            _span("07700 900000", 11, "PHONE_NUMBER"),
        ]

        _, phone = self._resolve(
            "x" * 23, spans, structure=structure, tables=tables
        )

        self.assertEqual(
            phone.redaction_type, Redaction.RedactionType.DS_INFORMATION
        )
        self.assertIn("table row", phone.rationale)

    # ---- everything uncertain stays third-party ----

    def test_a_third_partys_detail_stays_third_party(self):
        text = "SMITH, Jane\t07700 900111"
        spans = [
            _span("SMITH, Jane", 0, "PERSON_NAME"),
            _span("07700 900111", 12, "PHONE_NUMBER"),
        ]

        name, phone = self._resolve(text, spans)

        for result in (name, phone):
            self.assertEqual(
                result.redaction_type, Redaction.RedactionType.THIRD_PARTY_PII
            )
            self.assertFalse(result.is_accepted)
            self.assertIsNone(result.decided_by)
            self.assertIsNone(result.rationale)

    def test_a_shared_surname_is_not_resolved_to_the_data_subject(self):
        """
        The live disclosure bug Slice 1 fixed, re-asserted through resolution:
        "Bloggs" alone could be a relative, so neither the name nor anything
        near it may be treated as the data subject's.
        """
        text = "Bloggs\t07700 900111"
        spans = [
            _span("Bloggs", 0, "PERSON_NAME"),
            _span("07700 900111", 7, "PHONE_NUMBER"),
        ]

        name, phone = self._resolve(text, spans)

        self.assertEqual(
            name.redaction_type, Redaction.RedactionType.THIRD_PARTY_PII
        )
        self.assertEqual(
            phone.redaction_type, Redaction.RedactionType.THIRD_PARTY_PII
        )

    def test_two_people_in_a_block_leaves_the_detail_third_party(self):
        text = "Joe Bloggs and SMITH, Jane on 07700 900000"
        spans = [
            _span("Joe Bloggs", 0, "PERSON_NAME"),
            _span("SMITH, Jane", 15, "PERSON_NAME"),
            _span("07700 900000", 30, "PHONE_NUMBER"),
        ]

        *_, phone = self._resolve(text, spans)

        self.assertEqual(
            phone.redaction_type, Redaction.RedactionType.THIRD_PARTY_PII
        )

    def test_a_typeless_name_beside_the_data_subject_is_not_disclosed(self):
        """
        SpanCat reports no entity type and is trained largely on names. Such a
        span must never be attributed as a detail — doing so would relabel a
        third party's name as the data subject's and disclose it.
        """
        text = "Joe Bloggs spoke to Jane Smith"
        spans = [
            _span("Joe Bloggs", 0, "PERSON_NAME"),
            _span("Jane Smith", 20, None),
        ]

        _, other = self._resolve(text, spans)

        self.assertEqual(
            other.redaction_type, Redaction.RedactionType.THIRD_PARTY_PII
        )
        self.assertFalse(other.is_accepted)

    def test_an_unknown_label_falls_back_to_third_party(self):
        [result] = self._resolve("mystery", [_span("mystery", 0, label="???")])

        self.assertEqual(
            result.redaction_type, Redaction.RedactionType.THIRD_PARTY_PII
        )

    # ---- operational markings are never reattributed ----

    def test_operational_span_in_the_data_subjects_block_stays_operational(
        self,
    ):
        text = "Joe Bloggs\t#0723222"
        spans = [
            _span("Joe Bloggs", 0, "PERSON_NAME"),
            _span(
                "#0723222",
                11,
                "UK_COLLAR_NUMBER",
                label="OPERATIONAL",
            ),
        ]

        _, collar = self._resolve(text, spans)

        self.assertEqual(
            collar.redaction_type, Redaction.RedactionType.OPERATIONAL_DATA
        )
        self.assertFalse(collar.is_accepted)
        self.assertIsNone(collar.rationale)

    def test_an_operational_span_matching_the_ds_name_stays_operational(self):
        """What makes it redactable is the marking, not whose record it is in."""
        spans = [_span("Joe Bloggs", 0, "PERSON_NAME", label="OPERATIONAL")]

        [result] = self._resolve("Joe Bloggs", spans)

        self.assertEqual(
            result.redaction_type, Redaction.RedactionType.OPERATIONAL_DATA
        )

    # ---- documents and cases with nothing to resolve against ----

    def test_without_extracted_text_attribution_is_skipped(self):
        """
        Pre-attribution behaviour, unchanged: a record match still resolves,
        but nothing is inferred from layout that was never supplied.
        """
        spans = [
            _span("Joe Bloggs", 0, "PERSON_NAME"),
            _span("07700 900000", 11, "PHONE_NUMBER"),
        ]

        name, phone = resolve_spans(spans, _case())

        self.assertEqual(
            name.redaction_type, Redaction.RedactionType.DS_INFORMATION
        )
        self.assertEqual(
            phone.redaction_type, Redaction.RedactionType.THIRD_PARTY_PII
        )

    def test_a_case_with_no_data_subject_resolves_nothing_to_them(self):
        text = "Joe Bloggs\t07700 900000"
        spans = [
            _span("Joe Bloggs", 0, "PERSON_NAME"),
            _span("07700 900000", 11, "PHONE_NUMBER"),
        ]

        results = self._resolve(text, spans, case=_case(name=None, dob=None))

        for result in results:
            self.assertEqual(
                result.redaction_type, Redaction.RedactionType.THIRD_PARTY_PII
            )

    # ---- a human correction outranks the layout ----

    def test_text_ruled_third_party_is_not_proposed_again(self):
        """
        Story 13: a correction has to stick, or the reviewer re-makes it on
        every document in the case.
        """
        text = "Joe Bloggs\t07700 900000"
        spans = [
            _span("Joe Bloggs", 0, "PERSON_NAME"),
            _span("07700 900000", 11, "PHONE_NUMBER"),
        ]

        _, phone = self._resolve(
            text, spans, ruled_third_party={"07700 900000"}
        )

        self.assertEqual(
            phone.redaction_type, Redaction.RedactionType.THIRD_PARTY_PII
        )
        self.assertIsNone(phone.rationale)

    def test_the_ruling_is_matched_regardless_of_case(self):
        text = "Joe Bloggs\tJOE@EXAMPLE.COM"
        spans = [
            _span("Joe Bloggs", 0, "PERSON_NAME"),
            _span("JOE@EXAMPLE.COM", 11, "EMAIL_ADDRESS"),
        ]

        _, email = self._resolve(
            text, spans, ruled_third_party={"joe@example.com"}
        )

        self.assertEqual(
            email.redaction_type, Redaction.RedactionType.THIRD_PARTY_PII
        )

    def test_a_ruling_does_not_suppress_a_case_record_match(self):
        """
        Only inference is suppressed. The name held on the case record is not
        a guess, so a stray third-party ruling cannot override it.
        """
        spans = [_span("Joe Bloggs", 0, "PERSON_NAME")]

        [name] = self._resolve(
            "Joe Bloggs", spans, ruled_third_party={"Joe Bloggs"}
        )

        self.assertEqual(
            name.redaction_type, Redaction.RedactionType.DS_INFORMATION
        )
        self.assertTrue(name.is_accepted)

    def test_a_ruling_on_other_text_changes_nothing(self):
        text = "Joe Bloggs\t07700 900000"
        spans = [
            _span("Joe Bloggs", 0, "PERSON_NAME"),
            _span("07700 900000", 11, "PHONE_NUMBER"),
        ]

        _, phone = self._resolve(
            text, spans, ruled_third_party={"07700 999999"}
        )

        self.assertEqual(
            phone.redaction_type, Redaction.RedactionType.DS_INFORMATION
        )

    def test_no_spans_resolves_to_nothing(self):
        self.assertEqual(self._resolve("some text", []), [])
