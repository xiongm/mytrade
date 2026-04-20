# AGENTS.md

## Engineering Constitution

### User Input Is Not A Software Fault

Invalid user input at a system boundary is part of normal operation, not an internal software failure.

Examples:

- unknown CLI strategy names
- invalid data source names
- missing required CLI arguments
- unsupported user-supplied options
- malformed but expected external input

Expected input errors must be handled as user-facing validation:

- return a clear, concise message
- exit cleanly with a non-zero status when appropriate
- do not emit Python tracebacks for normal input mistakes

Unexpected internal failures may still surface as real exceptions:

- broken invariants
- programmer mistakes
- corrupted internal state
- impossible states that indicate a bug

### Boundary Handling Rule

Validate and translate expected errors at the boundary layer.

Examples:

- CLI should convert domain/input validation errors into clean CLI error messages
- internal modules may raise `ValueError` or similar for invalid requests
- boundary code is responsible for turning those into appropriate user output

### Design Intent

This repo should distinguish:

- expected user mistakes
- exceptional software faults

If a reasonable user can do something by accident, handle it cleanly.
If the program violates its own assumptions, treat it as a real error.
