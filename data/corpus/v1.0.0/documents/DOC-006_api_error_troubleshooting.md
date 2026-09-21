# API error troubleshooting guide

- **Document ID:** DOC-006
- **Version:** 3.0
- **Date:** 2026-07-05
- **Status:** current
- **Language:** en

## First checks
`DOC-006#SEC-01`

Capture the HTTP status, OrbeFlow error code, request_id, endpoint, and API version. A 4xx response is not automatically safe to retry. Compare the request against the current endpoint contract and confirm the workspace environment.

PX-1047 means the JSON body passed transport checks but failed schema validation. Typical causes are a missing required field, a string where a decimal is expected, or an unsupported enum value. The response contains a field_path when validation reaches a specific property.

## Authentication errors
`DOC-006#SEC-02`

AU-4012 indicates an expired or not-yet-valid OAuth access token. Refresh it once and retry the original request with the same idempotency key. AU-4038 means the token is valid but lacks the required scope or workspace role. Refreshing an unchanged grant will not fix AU-4038.

SG-4410 indicates a webhook signature mismatch and applies to inbound signed callbacks, not ordinary bearer-token API calls.

## Rate and availability
`DOC-006#SEC-03`

RL-4290 means the request exceeded a rate bucket. Honor Retry-After and add jitter. Do not create a new idempotency key for the retry. SV-5032 indicates temporary service unavailability; retry up to three times for idempotent requests. If it persists across two regions or for more than ten minutes, check service status and open a support case.

## Escalation package
`DOC-006#SEC-04`

Provide request_id, UTC timestamp, endpoint, version, response status, OrbeFlow code, and a redacted payload shape. Do not include bearer tokens, client secrets, signed webhook values, or unredacted personal data. If the failure occurs only on one workflow revision, include its FLW identifier.

## Audience and prerequisites
`DOC-006#SEC-05`

This document is for people who operate or administer OrbeFlow and already understand workspaces, environments, and platform identifiers. It assumes authorized access to the cited records; investigation never grants broader access by itself. Its specific focus is repeatable diagnosis, minimum evidence, and safe escalation. Before acting, confirm production versus sandbox, active plan, region, and the revision or version shown by the evidence. The same display name may exist in several environments. A successful sandbox action must be reviewed again before production use. When a required role is unavailable, preserve evidence and route the case to the accountable owner instead of bypassing Access Gate controls.

## Minimum evidence
`DOC-006#SEC-06`

Record UTC time, region, workspace, environment, relevant identifiers, and the observed result. For runs, combine event_id, RUN-, workflow_id, and revision. For tasks, include TSK- and state. For connections, include CON- and provider but never a secret. Copy codes such as PX-1047 or RL-4290 exactly. A screenshot may omit structured fields, so prefer a redacted export or machine-readable response. State when an identifier is missing rather than inventing it. Remove personal or commercial content that is not needed for diagnosis. The final record should allow another operator to reproduce the analysis without relying on the original investigator's memory.

## Operational example
`DOC-006#SEC-07`

Consider a request about “API error troubleshooting guide.” The operator first bounds the time and environment, locates the object by stable identifier, and compares expected with observed behavior. If they differ, the operator records one hypothesis and selects the lowest-risk check. A description without an exact code may resemble several articles, so object type and current state are decisive. If evidence points to another domain, transfer the case with its timeline intact. Repeating an operation with a new identifier before understanding idempotency can create external duplicates, hide the first failure, or make later reconciliation ambiguous.

## Boundaries and exceptions
`DOC-006#SEC-08`

This document does not authorize a plan change, weaker security control, record deletion, or access to unredacted content. Confirm commercial values and operational limits in the current catalog even when historical release notes contain numbers. An exception needs a reason, expiration, owner, and risk-appropriate approval. Authentication, retention, and residency exceptions require Security Admin participation. Emergency approval may accelerate incident mitigation but still requires later review. If two current sources appear inconsistent, stop the action and open a documentation correction instead of selecting the more convenient value.

## Validation and related documents
`DOC-006#SEC-09`

Finish by confirming that the expected result occurred and that another module was not harmed. For changes, compare a before and after window. For support, reproduce only when safe. For policy questions, confirm effective date and version. Useful related documents include DOC-020, DOC-012. A relationship supplies context, not automatic precedence. Current policy overrides an operational guide, the current catalog overrides historical release notes, and object evidence overrides assumptions based on display names. Record the section identifier used so later evaluation can distinguish the correct evidence from a passage that is merely semantically similar.
