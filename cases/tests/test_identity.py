from datetime import date

from django.test import SimpleTestCase

from cases.identity import (
    IdentityMatch,
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
