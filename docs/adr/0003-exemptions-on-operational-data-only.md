# Exemptions are chosen on accept, for Operational Data only

Exemptions were first offered on **reject**, recorded as the reason a suggestion was left in the clear. That reads backwards against practice: text is withheld *under* an exemption, so the exemption belongs with the accepted redaction, and disclosing text needs no reason at all. Exemptions are therefore chosen on accept, and reject is a single click with no reason.

Only Operational Data carries an exemption. Third-Party PII is withheld by default and Data Subject Information is disclosed, so neither has a basis to record; choosing an exemption on any suggestion accepts it as Operational Data. The exemption is stored as the template's name in the existing `justification` text, rather than a new link to the template, so the mechanism already in place is moved instead of replaced. Rows rejected before this change keep their old reasons.
