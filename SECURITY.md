# Security policy

## Release status

This is an early public release intended for controlled development and test
environments. It exposes operations that can read and modify PeopleTools
metadata and can cause database DDL to be executed. It is not safe to expose
directly to the public internet or to untrusted callers.

## Known limitation

The `AI_QUERY_RECORD_POST` implementation dynamically constructs SQL using
caller-supplied record names, field names, and filter operators. These inputs
are not yet protected by a complete allowlist and bind-variable design. Treat
this operation as unsafe for untrusted input.

Until this is corrected:

- deploy only in an isolated, non-production environment;
- do not grant the service operation to untrusted users;
- disable `AI_QUERY_RECORD_POST` when record querying is not required;
- use a dedicated least-privilege permission list instead of a broad delivered
  administrator permission list;
- keep Integration Broker endpoints behind the organization's trusted network;
- back up affected definitions before enabling write or build operations.

SQL and metadata writes run with permissions available to the PeopleSoft
application Access ID and can bypass normal component processing behavior.

## Credentials and reports

Do not commit PeopleSoft passwords, PS tokens, environment configuration,
compare reports, build logs, or runtime backups. Use placeholders in examples
and local configuration outside the repository.

When a GitHub repository is available, security reports should be submitted
privately through GitHub Security Advisories rather than opened as public
issues.
