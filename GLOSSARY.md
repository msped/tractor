# Tractor

Redaction of documents disclosed in response to subject access requests: what the data subject receives, and what is withheld from them.

## People

**Data Subject (DS)**:
The person whose personal data a case is about, and to whom the disclosure is made.
_Avoid_: Requestor, requester, applicant

**Reporting Person (RP)**:
The person who raised the matter a record is about. A data subject may or may not be the reporting person on any given record.
_Avoid_: Reporter, informant, complainant

**Role**:
The capacity in which a person appears on one record, such as reporting person or subject of the matter. A role belongs to the record, not to the case, so the same data subject can hold different roles across a case's documents.
_Avoid_: Designation, involvement type

## Source documents

**Record**:
A single matter documented by a source system, such as an incident, a complaint or a referral, together with the people involved in it.
_Avoid_: Occurrence, incident (these name one source system's kind of record)

**Role-dependent Field**:
A field of a record whose disclosure to the data subject depends on the data subject's role on that record.
_Avoid_: Conditional field, RP field

## Redaction

**Operational Data**:
Information about how the organisation operates, such as internal references or methods, withheld from the data subject under an exemption.
_Avoid_: Internal data, op data

**Third-Party PII**:
Personal data about anyone other than the data subject. It is withheld by default and needs no exemption.
_Avoid_: Third-party data, PII on its own

**Data Subject Information**:
The data subject's own personal data. It is disclosed to them, never withheld.
_Avoid_: DS data, requester data

**Exemption**:
The stated basis for withholding a redaction, chosen from a list the organisation maintains when the redaction is accepted. Choosing one does not change the redaction's type.
_Avoid_: Rejection reason, justification
