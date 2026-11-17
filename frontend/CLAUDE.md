# Frontend conventions

- Each component lives in its own directory with an `index.js` re-export:
  ```
  components/ComponentName/
  ├── ComponentName.js
  ├── ComponentName.cy.js   # Cypress component test (component testing, not E2E)
  └── index.js              # export * from './ComponentName';
  ```
- Import through the directory with the `@/` alias (`@/*` → `src/*`): `import { ComponentName } from "@/components/ComponentName"`
