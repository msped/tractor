from datetime import date

from django.test import SimpleTestCase

from cases.identity import (
    IdentityMatch,
    find_identity_occurrences,
    match_person,
    matches_dob_text,
    name_tokens,
)

DS_NAME = "Joe Bloggs"
DS_DOB = date(1990, 1, 1)


class MatchPersonNameTests(SimpleTestCase):
    """Identity from a name alone."""

    def assertVerdict(self, name, expected, ds_name=DS_NAME):
        self.assertIs(match_person(name, ds_name=ds_name), expected)

    def test_identical_name_matches(self):
        self.assertVerdict("Joe Bloggs", IdentityMatch.MATCH)

    def test_case_differences_match(self):
        self.assertVerdict("JOE BLOGGS", IdentityMatch.MATCH)
        self.assertVerdict("joe bloggs", IdentityMatch.MATCH)

    def test_surname_first_ordering_matches(self):
        """The format a source system prints must not change the answer."""
        self.assertVerdict("BLOGGS, JOE", IdentityMatch.MATCH)
        self.assertVerdict("Bloggs,Joe", IdentityMatch.MATCH)

    def test_punctuation_differences_match(self):
        self.assertVerdict(
            "O'Brien, Sinead", IdentityMatch.MATCH, ds_name="Sinead OBrien"
        )
        self.assertVerdict(
            "Smith Jones, Ann",
            IdentityMatch.MATCH,
            ds_name="Ann Smith-Jones",
        )

    def test_honorific_is_ignored(self):
        self.assertVerdict("Mr Joe Bloggs", IdentityMatch.MATCH)
        self.assertVerdict("Dr. Joe Bloggs", IdentityMatch.MATCH)

    def test_shared_surname_is_ambiguous_not_matched(self):
        """
        The live disclosure bug: a bare surname shared with the data subject
        must not be treated as the data subject, because it is very often a
        relative in the same case.
        """
        self.assertVerdict("Bloggs", IdentityMatch.AMBIGUOUS)

    def test_forename_alone_is_ambiguous(self):
        self.assertVerdict("Joe", IdentityMatch.AMBIGUOUS)

    def test_span_covering_a_second_person_is_ambiguous(self):
        """A span that swallows a third party is not the data subject."""
        self.assertVerdict(
            "Joe Bloggs and Jane Smith", IdentityMatch.AMBIGUOUS
        )

    def test_partial_overlap_is_ambiguous(self):
        self.assertVerdict("Joe Smith", IdentityMatch.AMBIGUOUS)

    def test_unrelated_name_does_not_match(self):
        self.assertVerdict("Jane Smith", IdentityMatch.NO_MATCH)

    def test_initial_alone_is_not_evidence(self):
        self.assertVerdict("J", IdentityMatch.NO_MATCH)
        self.assertVerdict("J.", IdentityMatch.NO_MATCH)

    def test_empty_inputs_do_not_match(self):
        self.assertVerdict("", IdentityMatch.NO_MATCH)
        self.assertVerdict("   ", IdentityMatch.NO_MATCH)
        self.assertVerdict("Joe Bloggs", IdentityMatch.NO_MATCH, ds_name="")
        self.assertVerdict("Joe Bloggs", IdentityMatch.NO_MATCH, ds_name=None)


class MatchPersonDobTests(SimpleTestCase):
    """A date of birth corroborates or refutes — it never establishes alone."""

    def test_agreeing_dob_keeps_a_name_match(self):
        self.assertIs(
            match_person("Joe Bloggs", DS_DOB, ds_name=DS_NAME, ds_dob=DS_DOB),
            IdentityMatch.MATCH,
        )

    def test_agreeing_dob_resolves_an_ambiguous_name(self):
        """A shared surname plus the right date of birth is the data subject."""
        self.assertIs(
            match_person("Bloggs", DS_DOB, ds_name=DS_NAME, ds_dob=DS_DOB),
            IdentityMatch.MATCH,
        )

    def test_conflicting_dob_blocks_a_name_match(self):
        """
        Two people with the same name and different dates of birth are
        different people — the case the requesting org's example turns on.
        """
        self.assertIs(
            match_person(
                "Joe Bloggs",
                date(1990, 1, 2),
                ds_name=DS_NAME,
                ds_dob=DS_DOB,
            ),
            IdentityMatch.NO_MATCH,
        )

    def test_conflicting_dob_blocks_an_ambiguous_name(self):
        self.assertIs(
            match_person(
                "Bloggs", date(1972, 6, 30), ds_name=DS_NAME, ds_dob=DS_DOB
            ),
            IdentityMatch.NO_MATCH,
        )

    def test_agreeing_dob_does_not_rescue_an_unrelated_name(self):
        self.assertIs(
            match_person("Jane Smith", DS_DOB, ds_name=DS_NAME, ds_dob=DS_DOB),
            IdentityMatch.NO_MATCH,
        )

    def test_document_supplying_no_dob_falls_back_to_the_name(self):
        self.assertIs(
            match_person("Joe Bloggs", None, ds_name=DS_NAME, ds_dob=DS_DOB),
            IdentityMatch.MATCH,
        )
        self.assertIs(
            match_person("Bloggs", None, ds_name=DS_NAME, ds_dob=DS_DOB),
            IdentityMatch.AMBIGUOUS,
        )

    def test_case_with_no_stored_dob_falls_back_to_the_name(self):
        self.assertIs(
            match_person("Joe Bloggs", DS_DOB, ds_name=DS_NAME, ds_dob=None),
            IdentityMatch.MATCH,
        )


class NameTokensTests(SimpleTestCase):
    def test_order_free(self):
        self.assertEqual(name_tokens("BLOGGS, Joe"), name_tokens("joe bloggs"))

    def test_apostrophe_closes_up_rather_than_splitting(self):
        """ "O'Bloggs" is one name, not an "o" and a "bloggs"."""
        self.assertEqual(name_tokens("O'Bloggs"), frozenset({"obloggs"}))
        self.assertEqual(name_tokens("O'Bloggs"), name_tokens("OBLOGGS"))

    def test_hyphen_splits(self):
        self.assertEqual(
            name_tokens("Smith-Jones"), frozenset({"smith", "jones"})
        )

    def test_single_characters_dropped(self):
        self.assertEqual(name_tokens("A Smith"), frozenset({"smith"}))

    def test_honorific_kept_when_it_is_the_whole_name(self):
        """ "Miss" can be a surname — never reduce a name to nothing."""
        self.assertEqual(name_tokens("Miss"), frozenset({"miss"}))

    def test_blank_name_has_no_tokens(self):
        self.assertEqual(name_tokens(""), frozenset())
        self.assertEqual(name_tokens(None), frozenset())


class MatchesDobTextTests(SimpleTestCase):
    """A span that is the date itself rather than a person."""

    def test_recognised_formats(self):
        for text in (
            "01/01/1990",
            "01-01-1990",
            "1990-01-01",
            "1 January 1990",
            "01 January 1990",
            "1 Jan 1990",
            "  01/01/1990  ",
        ):
            with self.subTest(text=text):
                self.assertTrue(matches_dob_text(text, DS_DOB))

    def test_other_dates_do_not_match(self):
        self.assertFalse(matches_dob_text("02/01/1990", DS_DOB))
        self.assertFalse(matches_dob_text("not a date", DS_DOB))

    def test_no_stored_dob_never_matches(self):
        self.assertFalse(matches_dob_text("01/01/1990", None))

    def test_blank_text_never_matches(self):
        self.assertFalse(matches_dob_text("", DS_DOB))
        self.assertFalse(matches_dob_text("   ", DS_DOB))


class FindIdentityOccurrencesTests(SimpleTestCase):
    """Locating the data subject inside text a detector claimed wholesale."""

    def find(self, text, ds_name=DS_NAME, ds_dob=None):
        return find_identity_occurrences(text, ds_name=ds_name, ds_dob=ds_dob)

    def matched(self, text, **kwargs):
        return [text[start:end] for start, end in self.find(text, **kwargs)]

    def test_finds_the_name_mid_sentence(self):
        text = "Witness statement obtained from Joe Bloggs (Witness)."

        self.assertEqual(self.matched(text), ["Joe Bloggs"])

    def test_finds_a_surname_first_name_from_a_forename_first_record(self):
        """The real shape: the record says 'Grace Hughes', the document does not."""
        text = "Witness statement obtained from HUGHES, GRACE (Witness)."

        self.assertEqual(
            self.matched(text, ds_name="Grace Hughes"), ["HUGHES, GRACE"]
        )

    def test_offsets_point_at_the_name(self):
        text = "Witness statement obtained from HUGHES, GRACE (Witness)."

        [(start, end)] = self.find(text, ds_name="Grace Hughes")

        self.assertEqual(text[start:end], "HUGHES, GRACE")
        self.assertEqual(start, text.index("HUGHES"))

    def test_finds_every_occurrence(self):
        text = "Joe Bloggs called. Later Bloggs, Joe called again."

        self.assertEqual(self.matched(text), ["Joe Bloggs", "Bloggs, Joe"])

    def test_ignores_a_shared_surname_alone(self):
        """A relative sharing the surname is not the data subject."""
        text = "Spoke to Bloggs about the incident."

        self.assertEqual(self.matched(text), [])

    def test_ignores_a_forename_alone(self):
        self.assertEqual(self.matched("Spoke to Joe about it."), [])

    def test_ignores_a_longer_hyphenated_surname(self):
        """'Bloggs' inside 'Bloggs-Smith' is a different person."""
        text = "Spoke to Joe Bloggs-Smith about it."

        self.assertEqual(self.matched(text), [])

    def test_ignores_a_name_embedded_in_a_longer_word(self):
        self.assertEqual(self.matched("See joebloggs for details."), [])

    def test_stops_at_the_complete_name_not_the_following_word(self):
        text = "Joe Bloggs Smith attended."

        self.assertEqual(self.matched(text), ["Joe Bloggs"])

    def test_honorific_is_not_included_in_the_match(self):
        text = "Mr Joe Bloggs attended."

        self.assertEqual(self.matched(text), ["Joe Bloggs"])

    def test_apostrophes_are_matched_across_spellings(self):
        text = "Statement from O'BRIEN, John."

        self.assertEqual(
            self.matched(text, ds_name="John OBrien"), ["O'BRIEN, John"]
        )

    def test_finds_the_dob_inside_a_wider_string(self):
        text = "DOB recorded as 01/01/1990 on the file."

        self.assertEqual(self.matched(text, ds_dob=DS_DOB), ["01/01/1990"])

    def test_ignores_a_different_date(self):
        text = "DOB recorded as 02/03/1988 on the file."

        self.assertEqual(self.matched(text, ds_dob=DS_DOB), [])

    def test_ignores_a_date_embedded_in_a_longer_number(self):
        text = "Reference 101/01/19901 on the file."

        self.assertEqual(self.matched(text, ds_dob=DS_DOB), [])

    def test_finds_both_a_name_and_a_dob(self):
        text = "Joe Bloggs, born 01/01/1990, attended."

        self.assertEqual(
            self.matched(text, ds_dob=DS_DOB), ["Joe Bloggs", "01/01/1990"]
        )

    def test_overlapping_dob_formats_are_merged_once(self):
        """Several formats can render the same characters; one range comes back."""
        text = "Born 01/01/1990 exactly."

        self.assertEqual(len(self.find(text, ds_dob=DS_DOB)), 1)

    def test_no_record_finds_nothing(self):
        self.assertEqual(self.find("Joe Bloggs attended.", ds_name=None), [])

    def test_empty_text_finds_nothing(self):
        self.assertEqual(self.find(""), [])
        self.assertEqual(self.find(None), [])

    def test_results_are_sorted_by_position(self):
        text = "Born 01/01/1990. Name Joe Bloggs."

        starts = [start for start, _ in self.find(text, ds_dob=DS_DOB)]

        self.assertEqual(starts, sorted(starts))
