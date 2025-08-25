# Remediation Log

This log tracks all security and accessibility issues identified and resolved during the audit process in preparation for service approval.

| Issue ID | Status | Priority | GDS Principle | Description | Solution |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **SEC-001** | `Todo` | `Moderate` | Security | `torch` package had a Denial-of-Service vulnerability [GHSA-887c-mr87-cxwp](https://github.com/advisories/GHSA-887c-mr87-cxwp). | Upgrade upon new release. |
| **AX-001** | `Done` | `High` | Accessibility | The file upload modal was not keyboard accessible. The dropzone could not be focused or activated. | Implemented `tabIndex="0"` and keyboard event listeners (`Enter`/`Space`) to trigger the file input. |
| **AX-002** | `Done` | `Medium` | Accessibility | White text on an orange button (`#ed6c02`) had a contrast ratio of 3.11, failing WCAG AA. | Darkened the background orange to `#b55401` to achieve a compliant contrast ratio of 4.7:1. |
