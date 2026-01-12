# Tractor

Welcome to the Tractor documentation.

Tractor is a document redaction application with ML-powered Named Entity Recognition. Users upload documents, the system identifies sensitive information using spaCy NER, and users can accept/reject redactions before exporting redacted versions.

## Key Features

- **Document Upload**: Support for PDF and docx files.
- **Automatic Redaction**: ML-powered Named Entity Recognition identifies sensitive information
- **Review Workflow**: Accept or reject suggested redactions
- **Model Training**: Train custom models from accepted redactions
- **Export**: Generate disclosure packages with original, redacted, and edited versions

## Quick Links

- [Getting Started](user-guide/getting-started.md) - Set up and start using Tractor
- [Redacting Documents](user-guide/redaction.md) - Learn how to redact documents
- [Developer Setup](dev/setup.md) - Set up your development environment
- [Architecture](dev/architecture.md) - Understand how Tractor works

## License

Tractor is licensed under the [AGPL-3.0 License](https://github.com/msped/tractor/blob/main/LICENSE).
