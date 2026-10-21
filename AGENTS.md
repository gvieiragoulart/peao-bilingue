# Agent instructions

Use Context7 MCP for current documentation whenever the user asks about a
library, framework, SDK, API, CLI tool, or cloud service, including syntax,
configuration, migration, setup, and library-specific debugging. Start with
`resolve-library-id` using the library name and topic unless the user provides
an exact `/org/project` ID. Pick the best relevant, reputable match, using a
version-specific ID when needed. Call `query-docs` for each distinct concept
and answer from those docs. This does not apply to ordinary refactoring,
business logic debugging, code review, or scripts written from scratch.

When asked to update the user's preferences, searches, CV, profile notes, or
other configuration in a running Peão Bilíngue Linux window, read
[`skills/peao-local-control/SKILL.md`](skills/peao-local-control/SKILL.md)
and use the local control CLI. The protocol is documented in
[`docs/local-control.md`](docs/local-control.md).
