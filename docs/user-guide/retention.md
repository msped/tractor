# Retention Review

The Retention Review page gives administrators visibility over cases that are approaching or have passed their retention date, and lets them delete those cases manually when automatic deletion is disabled.

## How retention dates work

Every case has a retention date calculated automatically when the case is created:

- **Adult data subjects** — retention date is `CASE_RETENTION_YEARS` years after the case creation date (default: 6 years).
- **Minor data subjects** — retention date is the data subject's 18th birthday plus `CASE_RETENTION_YEARS` years.

Once a case passes its retention date it is either deleted automatically (if `AUTO_CASE_DELETION_ENABLED=true`) or surfaced on the Retention Review page for manual action.

## Automatic vs manual deletion

| Mode | How to enable | What happens |
|------|--------------|--------------|
| **Automatic** | `AUTO_CASE_DELETION_ENABLED=true` (default) | A scheduled task runs daily and permanently deletes all cases whose retention date has passed. No manual action is required. |
| **Manual** | `AUTO_CASE_DELETION_ENABLED=false` | No automatic deletion occurs. Administrators must use the Retention Review page to delete overdue cases. |

The current mode is shown on the **Settings** page under the **Auto Case Deletion** card.

## Accessing the Retention Review page

Click **Retention Review** in the sidebar. This item is only visible to administrators.

## Understanding the table

The page shows two groups of cases, combined and sorted by retention date (earliest first):

| Group | Description |
|-------|-------------|
| **Overdue** | Cases whose retention date has already passed. |
| **Upcoming** | Cases whose retention date falls within the next `RETENTION_WARNING_DAYS` days (default: 30). |

If neither group contains any cases, the message "No cases require review." is shown.

### Columns

By default the table shows all available columns. Click the **column chooser** icon (top-left of the table) to hide columns you do not need:

| Column | Description |
|--------|-------------|
| Case reference | The unique reference assigned when the case was created. |
| Name | The data subject's name. |
| Date of birth | The data subject's date of birth, used to calculate retention for minors. |
| Retention date | The date on or after which the case is eligible for deletion. |
| Created date | When the case was first created. |
| Case outcome | The current status of the case (e.g. Completed, Closed). |

## Reviewing a case before deleting

Click the **open in new tab** icon on any row to open the case in a new browser tab. Review the case and its documents before deciding whether to delete it.

## Deleting cases

!!! warning
    Deletion is permanent and cannot be undone. All documents, redactions, and exports associated with a case are removed when it is deleted.

### Delete a single case

Click the **delete** icon on the case's row, then confirm the prompt.

### Delete multiple cases

1. Check the checkbox on each row you want to delete. Use the header checkbox to select all visible cases at once.
2. Click **Delete selected (N)** in the toolbar above the table.
3. Confirm the prompt.

A success notification confirms how many cases were deleted. The table refreshes automatically to reflect the changes.
