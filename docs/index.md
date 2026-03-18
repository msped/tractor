# Tractor

Welcome to the Tractor documentation.

Tractor is a document redaction application with ML-powered Named Entity Recognition. Users upload documents, the system identifies sensitive information using GLiNER and Presidio, and users can accept/reject redactions before exporting redacted versions.

## Key Features

- **Document Upload**: Support for PDF and docx files.
- **Automatic Redaction**: Hybrid three-model NER pipeline — SpanCat (trained), GLiNER (zero-shot), and Presidio (pattern-based)
- **Review Workflow**: Accept, reject, or bulk-action suggested redactions. Adjacent same-type spans are automatically merged for easier review.
- **Model Training**: Train custom SpanCat models from accepted redactions; GLiNER model managed separately
- **Export**: Generate disclosure packages with original, redacted, and edited versions

## Quick Links

- [Getting Started](user-guide/getting-started.md) - Set up and start using Tractor
- [Redacting Documents](user-guide/redaction.md) - Learn how to redact documents
- [Settings](user-guide/settings.md) - Configure exemption templates and other settings
- [Developer Setup](dev/setup.md) - Set up your development environment
- [Architecture](dev/architecture.md) - Understand how Tractor works

## License

Tractor is licensed under the [AGPL-3.0 License](https://github.com/msped/tractor/blob/main/LICENSE).
