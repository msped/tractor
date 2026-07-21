# Internal Review

Once a case has been disclosed — a disclosure package has been generated — its redactions are **locked**. This protects the record of what was actually disclosed and the decisions behind it.

If the data subject later challenges the disclosure, you can open an **internal review** to make targeted changes and re-disclose, without destroying the original disclosure or its decision record.

## The Disclosed & Locked State

After you generate a disclosure package, the case becomes **disclosed and locked**. A banner appears on the case page:

> **Disclosed & locked** — This case has been disclosed. Open an internal review to change its redactions and re-disclose.

While a case is locked, you cannot accept, reject, add, delete, or otherwise change redactions on any of its documents. The disclosed decisions are frozen exactly as they were exported.

!!! info
    Locking happens automatically the moment a disclosure package finishes generating. There is no separate "lock" action.

## Opening a Review

To make changes to a disclosed case, click **Open Review** on the locked banner.

This:

- Moves the case into the **Under Review** state
- Unlocks the redactions so you can edit them again
- Leaves every document marked as **Completed** — you do not have to re-review the whole case. Open only the one or two documents you need to change and edit them in place.

The banner changes to show the case is unlocked:

> **Under internal review — unlocked** — This case has been disclosed and is currently under review. Redaction changes are permitted and are being tracked against this review.

Only one review can be open on a case at a time.

## Making Changes During a Review

While a review is open, you edit redactions exactly as you would during normal review — accept, reject, retype, add manual redactions, adjust context, and so on. See [Redacting Documents](redaction.md) for the mechanics.

### Data Subject Information Propagation

Marking text as **Data Subject Information** normally propagates to matching text across every document in the case automatically. During a review, this is made explicit so you can see the impact before committing to it.

When you mark a new **DS Info** term while a review is open, a **Propagate data subject information?** dialog appears listing every other document that would gain redactions for that term, along with the number of matches in each. Click **Propagate** to apply the change across the case, or **Cancel** to leave the other documents untouched.

If no other document is affected, the dialog is skipped and the redaction is simply applied to the current document.

## Closing a Review

Every review must be closed, and closing always requires you to record an **outcome** — a short note explaining what the review decided. This becomes part of the case's permanent disclosure history.

There are two ways to close a review, both offered on the unlocked banner.

### Complete Review

Choose **Complete Review** when your changes should be disclosed. Tractor:

1. Regenerates the disclosure package to reflect the current redactions
2. Preserves the new package as a fresh entry in the disclosure history, attributed to this review
3. Re-locks the case

The original disclosure is **not** overwritten — it remains available in the disclosure history alongside the new one.

### Abandon Review

Choose **Abandon Review** when the challenge did not warrant a change. Tractor:

1. Discards every edit made during the review
2. Restores the redactions to exactly what was last disclosed
3. Re-locks the case

No new disclosure package is generated.

!!! warning
    Abandoning is irreversible — the edits made during the review are discarded, not saved anywhere. If you are unsure, complete the review instead and keep the record.

## Disclosure History

The **Disclosure History** panel on the case page lists every disclosure package the case has ever produced, newest first. Each row shows the disclosure's label and the time it was generated, and can be downloaded individually.

Disclosures produced by a review are tagged **From review**. Expand any row to see:

- The **review outcome** that produced it (for review-generated disclosures)
- A **diff** of the redaction changes it introduced compared with the previous disclosure — grouped into **Added**, **Removed**, and **Modified**, with per-field before/after detail for modified redactions

While a review is open, a leading **In progress** row previews the changes staged for the next disclosure, so you can review your edits before completing.

## Lifecycle Summary

| Case state          | Redactions | Available action        |
|---------------------|------------|-------------------------|
| Disclosed & locked  | Read-only  | Open Review             |
| Under review        | Editable   | Complete or Abandon     |

The guiding invariant: **when no review is open, the live redactions always match the most recent disclosure exactly.**
