# Remediation Log

This log tracks all security and accessibility issues identified and resolved during the audit process in preparation for service approval.

| Issue ID | Status | Priority | GDS Principle | Description | Solution |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **SEC-001** | `Todo` | `Moderate` | Security | `torch` package had a Denial-of-Service vulnerability [GHSA-887c-mr87-cxwp](https://github.com/advisories/GHSA-887c-mr87-cxwp). | Upgrade upon new release. |
| **AX-001** | `Done` | `High` | Accessibility | The file upload modal was not keyboard accessible. The dropzone could not be focused or activated. | Implemented `tabIndex="0"` and keyboard event listeners (`Enter`/`Space`) to trigger the file input. |
| **AX-002** | `Done` | `Medium` | Accessibility | White text on an orange button (`#ed6c02`) had a contrast ratio of 3.11, failing WCAG AA. | Darkened the background orange to `#b55401` to achieve a compliant contrast ratio of 4.7:1. |
| **AX-003** | `Done` | `High` | Accessibility | No `prefers-reduced-motion` support. Sidebar width, dashboard layout, and toolbar transitions fired regardless of user OS motion preference, affecting users with vestibular disorders. | Added `@media (prefers-reduced-motion: reduce)` rule to `globals.css` disabling all transitions and animations. |
| **AX-004** | `Done` | `Medium` | Accessibility | No skip navigation link. Keyboard users were required to tab through all sidebar items on every page load before reaching main content. | Added a visually hidden skip link as the first focusable element in the root layout, targeting `#main-content` on the dashboard layout. |
| **AX-005** | `Done` | `Medium` | Accessibility | Active navigation items had no `aria-current="page"` attribute. Active state was communicated visually only, providing no semantic signal to screen readers. | Added `aria-current="page"` to all active `ListItemButton` elements in `NavSidebar`. |
| **AX-006** | `Done` | `Low` | Accessibility | Login form fields lacked `autocomplete` attributes, preventing password managers from autofilling credentials. | Added `autocomplete="username"` and `autocomplete="current-password"` to the respective fields in `LoginComponent`. |
