# Testing

Run the suites through the Makefile: `make be-test`, `make be-test-cov` (90% threshold), `make fe-cy-run`, `make fe-cy-test` (80% threshold).

## Backend

Tests live in `{app}/tests/`, one module per layer: `test_models.py`, `test_views.py`, `test_services.py`, `test_serializers.py`. Use freezegun for time.

### Network

Test classes mix in `NetworkBlockerMixin` so no test can reach the network. A test that hangs or fails with a blocked-socket error is reaching for a model download or an external service — mock the loader rather than lifting the block.

### Heavy NLP imports stay lazy

GLiNER, Presidio and pandas are imported inside the functions that use them, never at module level. Importing pandas' C extensions while freezegun is active crashes the test run. Ruff enforces this (`TID253` in `ruff.toml`).

### Where to mock

Patch a function at the module that defines it, not where it is imported:

| To stub out | Patch |
| --- | --- |
| GLiNER model load | `training.loader._load_gliner_model` (not `GLiNER.from_pretrained`) |
| SpanCat model load | `training.loader._load_spancat_model` |
| GLiNER extraction | `training.extractors.gliner_extractor.extract_with_gliner` |
| SpanCat extraction | `training.extractors.spancat_extractor.extract_with_spancat` |
| Presidio engines | `presidio_analyzer.AnalyzerEngine` and `presidio_analyzer.nlp_engine.NlpEngineProvider` |

## Frontend

Cypress component tests sit beside each component as `ComponentName.cy.js`.

`cy.type()` reads `{...}` as a key sequence. Type a literal brace as `{{`, so the regex `\d{4}` is written `'\\d{{4}}'`.
