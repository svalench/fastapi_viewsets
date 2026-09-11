Maintenance release fixing dependency metadata, source-distribution contents, and quickstart validation.

- Require SQLAlchemy 2.0 or newer, matching the APIs already used by the library; SQLAlchemy 1.4 is not supported.
- Include missing test fixtures and documentation support files in the source distribution.
- Add regression tests that execute the documented quickstarts.
- Validate installed-wheel examples in CI.
- Verify requested release versions against pyproject.toml before publishing.

Changes: https://github.com/svalench/fastapi_viewsets/pull/12
