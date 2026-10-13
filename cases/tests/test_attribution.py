from django.test import SimpleTestCase

from cases.attribution import (
    attribute_spans,
    is_attributable,
    is_person_span,
)
from cases.blocks import build_blocks


def _span(text, start, entity_type, label="THIRD_PARTY"):
    return {
        "text": text,
        "label": label,
        "start_char": start,
        "end_char": start + len(text),
        "entity_type": entity_type,
    }


class PersonSpanTests(SimpleTestCase):
    def test_detector_vocabularies_are_read_alike(self):
        """GLiNER reports its prompt label, Presidio its recognizer entity."""
        for entity_type in ("person name", "PERSON_NAME", "PERSON", "Person"):
            with self.subTest(entity_type=entity_type):
                self.assertTrue(
                    is_person_span(_span("BLOGGS, Joe", 0, entity_type))
                )

    def test_a_detail_is_not_a_person(self):
        self.assertFalse(
            is_person_span(_span("07700 900000", 0, "PHONE_NUMBER"))
        )

    def test_a_span_with_no_entity_type_is_not_a_person(self):
        """SpanCat and Gemma report no fine-grained type, so there is nothing to read."""
        self.assertFalse(is_person_span(_span("BLOGGS, Joe", 0, None)))


class AttributableSpanTests(SimpleTestCase):
    def test_recognised_detail_types_are_attributable(self):
        for entity_type in (
            "PHONE_NUMBER",
            "EMAIL_ADDRESS",
            "UK_POSTCODE",
            "UK_NHS",
            "UK_NI_NUMBER",
            "address",
            "date of birth",
        ):
            with self.subTest(entity_type=entity_type):
                self.assertTrue(is_attributable(_span("x", 0, entity_type)))

    def test_person_spans_are_not_attributable(self):
        """A name is matched against the case record, not attributed to itself."""
        self.assertFalse(
            is_attributable(_span("BLOGGS, Joe", 0, "PERSON_NAME"))
        )

    def test_unrecognised_and_missing_types_are_not_attributable(self):
        """
        Attribution grants disclosure, so a span whose kind is unknown has not
        earned it. SpanCat in particular reports no type and is trained largely
        on names — attributing one as a detail would hand a third party's name
        to the requester.
        """
        for entity_type in (None, "", "SOMETHING_CUSTOM"):
            with self.subTest(entity_type=entity_type):
                self.assertFalse(is_attributable(_span("x", 0, entity_type)))

    def test_location_and_organisation_are_not_details_of_a_person(self):
        """A town or employer near someone's name is not theirs to disclose."""
        for entity_type in ("location", "organisation"):
            with self.subTest(entity_type=entity_type):
                self.assertFalse(is_attributable(_span("x", 0, entity_type)))

    def test_operational_spans_are_never_attributable(self):
        """
        Whatever their type: what makes an operational marking redactable is
        the marking, not whose record it appears in.
        """
        self.assertFalse(
            is_attributable(
                _span("#0723222", 0, "UK_COLLAR_NUMBER", label="OPERATIONAL")
            )
        )
        self.assertFalse(
            is_attributable(
                _span("07700 900000", 0, "PHONE_NUMBER", label="OPERATIONAL")
            )
        )


class AttributeSpansTests(SimpleTestCase):
    def _blocks(self, text):
        return build_blocks(text, None, [])

    def test_lone_person_in_a_block_takes_its_details(self):
        text = "BLOGGS, Joe\t07700 900000\tjoe@example.com"
        person = _span("BLOGGS, Joe", 0, "PERSON_NAME")
        phone = _span("07700 900000", 12, "PHONE_NUMBER")
        email = _span("joe@example.com", 25, "EMAIL_ADDRESS")

        results = attribute_spans(self._blocks(text), [person, phone, email])

        self.assertEqual(
            [a.span["text"] for a in results],
            ["07700 900000", "joe@example.com"],
        )
        self.assertTrue(all(a.person is person for a in results))
        self.assertTrue(all(a.is_resolved for a in results))

    def test_two_people_in_a_block_resolves_nothing(self):
        """
        No tie-break and no nearest-name rule. Guessing would eventually
        attribute a third party's number to the data subject and disclose it.
        """
        text = "BLOGGS, Joe and SMITH, Jane on 07700 900000"
        spans = [
            _span("BLOGGS, Joe", 0, "PERSON_NAME"),
            _span("SMITH, Jane", 16, "PERSON_NAME"),
            _span("07700 900000", 31, "PHONE_NUMBER"),
        ]

        results = attribute_spans(self._blocks(text), spans)

        self.assertEqual(len(results), 1)
        self.assertIsNone(results[0].person)
        self.assertFalse(results[0].is_resolved)

    def test_block_with_no_person_resolves_nothing(self):
        text = "Contact number: 07700 900000"
        phone = _span("07700 900000", 16, "PHONE_NUMBER")

        results = attribute_spans(self._blocks(text), [phone])

        self.assertEqual(len(results), 1)
        self.assertIsNone(results[0].person)

    def test_person_in_a_different_block_is_not_borrowed(self):
        text = "BLOGGS, Joe\nContact: 07700 900000"
        person = _span("BLOGGS, Joe", 0, "PERSON_NAME")
        phone = _span("07700 900000", 21, "PHONE_NUMBER")

        results = attribute_spans(self._blocks(text), [person, phone])

        self.assertIsNone(results[0].person)

    def test_detail_straddling_a_block_boundary_resolves_nothing(self):
        text = "BLOGGS, Joe\n07700 900000"
        person = _span("BLOGGS, Joe", 0, "PERSON_NAME")
        straddling = _span("Joe\n07700 900000", 8, "PHONE_NUMBER")

        results = attribute_spans(self._blocks(text), [person, straddling])

        self.assertEqual(len(results), 1)
        self.assertIsNone(results[0].person)
        self.assertIsNone(results[0].block)

    def test_each_record_line_keeps_its_own_details(self):
        """The shape a pasted record export arrives in."""
        text = (
            "BLOGGS, Joe\t07700 900000\n"
            "HUGHES, Grace\t07700 900111\n"
            "SMITH, Jane\t07700 900222"
        )
        joe = _span("BLOGGS, Joe", 0, "PERSON_NAME")
        grace = _span("HUGHES, Grace", 25, "PERSON_NAME")
        jane = _span("SMITH, Jane", 52, "PERSON_NAME")
        spans = [
            joe,
            _span("07700 900000", 12, "PHONE_NUMBER"),
            grace,
            _span("07700 900111", 39, "PHONE_NUMBER"),
            jane,
            _span("07700 900222", 64, "PHONE_NUMBER"),
        ]

        results = attribute_spans(self._blocks(text), spans)

        self.assertEqual(
            [(a.span["text"], a.person["text"]) for a in results],
            [
                ("07700 900000", "BLOGGS, Joe"),
                ("07700 900111", "HUGHES, Grace"),
                ("07700 900222", "SMITH, Jane"),
            ],
        )

    def test_operational_span_in_someones_block_produces_no_entry(self):
        text = "BLOGGS, Joe\t#0723222\t07700 900000"
        spans = [
            _span("BLOGGS, Joe", 0, "PERSON_NAME"),
            _span("#0723222", 12, "UK_COLLAR_NUMBER", label="OPERATIONAL"),
            _span("07700 900000", 21, "PHONE_NUMBER"),
        ]

        results = attribute_spans(self._blocks(text), spans)

        self.assertEqual([a.span["text"] for a in results], ["07700 900000"])

    def test_table_row_groups_a_record_in_a_docx(self):
        """
        The DOCX path: cells of one row form the block, so a name in one cell
        takes the details in its sibling cells and not the row below's.
        """
        structure = [{"type": "table", "table_id": 0, "start": 0, "end": 60}]
        tables = [
            {
                "id": 0,
                "cells": [
                    {
                        "row": 0,
                        "col": 0,
                        "text": "BLOGGS, Joe",
                        "start": 0,
                        "end": 11,
                        "isMergedContinuation": False,
                    },
                    {
                        "row": 0,
                        "col": 1,
                        "text": "07700 900000",
                        "start": 12,
                        "end": 24,
                        "isMergedContinuation": False,
                    },
                    {
                        "row": 1,
                        "col": 0,
                        "text": "HUGHES, Grace",
                        "start": 25,
                        "end": 38,
                        "isMergedContinuation": False,
                    },
                    {
                        "row": 1,
                        "col": 1,
                        "text": "07700 900111",
                        "start": 39,
                        "end": 51,
                        "isMergedContinuation": False,
                    },
                ],
            }
        ]
        blocks = build_blocks("x" * 60, structure, tables)
        spans = [
            _span("BLOGGS, Joe", 0, "PERSON_NAME"),
            _span("07700 900000", 12, "PHONE_NUMBER"),
            _span("HUGHES, Grace", 25, "PERSON_NAME"),
            _span("07700 900111", 39, "PHONE_NUMBER"),
        ]

        results = attribute_spans(blocks, spans)

        self.assertEqual(
            [(a.span["text"], a.person["text"]) for a in results],
            [
                ("07700 900000", "BLOGGS, Joe"),
                ("07700 900111", "HUGHES, Grace"),
            ],
        )

    def test_no_blocks_resolves_nothing(self):
        phone = _span("07700 900000", 0, "PHONE_NUMBER")

        results = attribute_spans([], [phone])

        self.assertEqual(len(results), 1)
        self.assertIsNone(results[0].person)

    def test_no_spans_yields_no_attributions(self):
        self.assertEqual(attribute_spans(self._blocks("text here"), []), [])
