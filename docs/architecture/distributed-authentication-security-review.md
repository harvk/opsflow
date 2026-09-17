# Distributed Authentication Security Review

## Review status

This document records the Phase 10 security review of
service-to-service authentication between the OpsFlow Core
Backend and Incident Service.

The reviewed implementation uses independently signed,
short-lived RS256 JWT credentials in both directions. The
former shared token and custom internal-token header are not
supported authentication paths.

## Protected communication paths

| Caller | Receiver | Purpose | Required scope |
|---|---|---|---|
| Core Backend | Incident Service | Read incidents | `incidents:read` |
| Core Backend | Incident Service | Create, update, or delete incidents | `incidents:write` |
| Incident Service | Core Backend | Check service existence | `services:read` |

Browser credentials terminate at the Core Backend. The Core
Backend creates a separate service credential when it calls
Incident Service. Incident Service creates its own service
credential when it calls the private Core service-catalog
endpoint.

## Trust boundaries

| Asset | Trusted location | Prohibited locations |
|---|---|---|
| Core private key | Core Backend runtime | Incident Service, frontend, database, images, Git |
| Incident private key | Incident Service runtime | Core Backend, frontend, database, images, Git |
| Core public key | Incident Service verifier | No confidentiality requirement |
| Incident public key | Core Backend verifier | No confidentiality requirement |
| Browser access and refresh tokens | Core user-authentication boundary | Incident Service |

Docker Compose mounts file-backed secrets read-only. Private
key contents are not stored in environment variables. The
environment contains only secret-file paths and non-secret
identity metadata.

## Credential contract

An accepted service credential must satisfy all of these
conditions:

- JOSE algorithm is exactly `RS256`.
- JOSE type is exactly `JWT`.
- `kid` identifies a configured RSA public key.
- RSA key size is at least 2048 bits.
- `iss` matches the expected calling service.
- `sub` equals the expected issuer.
- `aud` matches the receiving service.
- `token_use` equals `service`.
- `jti`, `iat`, `nbf`, and `exp` are present and valid.
- Declared lifetime is between 30 and 120 seconds.
- Clock skew is configured between 0 and 30 seconds.
- `scope` is a non-empty set of registered service scopes.

Signature verification alone is insufficient. A correctly
signed token with the wrong audience, issuer, use, lifetime,
or scope contract is rejected.

## Authentication and authorization separation

Authentication establishes which service signed the request.
Authorization independently checks whether the authenticated
principal holds the scope required by the operation.

| Condition | Public response |
|---|---|
| Missing or invalid service credential | `401 Invalid service credentials.` |
| Valid credential without required scope | `403 Insufficient service permissions.` |

Detailed failure reasons remain internal and use a bounded
enumeration. Clients do not receive signature, claim, key, or
parser details that could serve as an authentication oracle.

## Threat coverage

| Threat | Control | Result |
|---|---|---|
| Forged credential | RS256 signature validation | Rejected |
| Algorithm confusion | Exact `RS256` allowlist | Rejected |
| HMAC/RSA confusion | RSA public-key loading and algorithm check | Rejected |
| Unknown signing key | Explicit `kid` mapping | Rejected |
| Cross-service token reuse | Exact issuer and audience | Rejected |
| Browser-token forwarding | Separate outbound service-token providers | Prevented by design and tests |
| Excessive privilege | Per-operation scopes | Rejected with `403` |
| Long-lived credential | Maximum token lifetime | Rejected |
| Premature or expired token | `nbf`, `iat`, and `exp` validation | Rejected |
| Shared-secret fallback | Static production-contract check | Blocked in CI |
| Private-key crossover | Compose and runtime boundary checks | Blocked in CI |
| Credential leakage through events | Structured bounded event schema | Excluded and tested |
| Unbounded metrics cardinality | Registered outcomes, reasons, and scopes | Prevented |

## Failure behavior

Verification fails closed. Missing configuration, unreadable
keys, invalid PEM data, non-RSA keys, weak RSA keys, malformed
credentials, and invalid claims do not produce an
authenticated principal.

Outbound gateways create a new scoped credential for the
operation being attempted. They do not reuse browser tokens or
the retired shared secret.

Unexpected downstream `401` or `403` responses are translated
at the Core gateway boundary instead of exposing downstream
authentication details to browser clients.

## Security observability

Both services expose bounded counters for:

- authentication success and failure;
- bounded authentication failure reason;
- authorization grant and denial;
- registered service scope.

Both services emit structured `service_authentication` and
`service_authorization` events. Events may contain a validated
request ID, bounded outcome, bounded reason, and registered
scope.

Events and metrics must not contain:

- bearer credentials;
- authorization headers;
- JWT payloads or claims;
- private or public key material;
- cookies or CSRF values;
- request bodies;
- arbitrary exception messages;
- user-controlled metric labels.

Failure of the security-event logging sink does not change the
authentication or authorization decision.

## Rotation behavior

Rotation support is direction-specific:

- Incident Service can temporarily trust current and previous
  Core public keys, supporting bounded Core signing-key
  overlap.
- Core Backend currently trusts one Incident public key.
  Incident signing-key rotation requires a coordinated
  deployment.

Neither direction permits an unknown `kid`. A private key must
never be replaced while retaining the old key ID.

## Explicit non-guarantees

The implementation does not claim:

- transport encryption on the local Compose bridge network;
- workload identity supplied by a cloud control plane;
- hardware-backed private-key storage;
- one-time token consumption;
- distributed `jti` replay prevention;
- per-request revocation of an already issued service JWT;
- zero-downtime Incident signing-key overlap rotation;
- protection after an owning service's private key is
  compromised.

A valid service credential may be replayed during its short
lifetime. Exposure is bounded by lifetime, audience, issuer,
scope, key protection, and clock-skew controls, but is not
eliminated.

Local Compose communication uses ordinary HTTP. Production
deployment should add encrypted transport or a platform
service mesh so application-level authentication and transport
confidentiality are both present.

## Compromise response

If a private service key may be compromised:

1. Treat the affected service identity as compromised.
2. Generate a new RSA keypair and new key ID.
3. Distribute the replacement public key through the approved
   secret-management path.
4. Deploy the receiving verifier configuration.
5. Deploy the replacement private signing key and key ID.
6. Remove trust in the compromised public key as soon as the
   deployment strategy permits.
7. Review bounded authentication failures and authorization
   decisions for abnormal activity.
8. Confirm that no key material appeared in logs, images, Git,
   or build artifacts.

The exact deployment order depends on whether the affected
direction supports overlapping verification keys.

## Automated evidence

The repository provides these evidence layers:

| Layer | Evidence |
|---|---|
| Static contract | Retired identifiers absent from production paths |
| Unit tests | Issuance, verification, claims, scopes, and loaders |
| Adversarial tests | Malformed, confused, wrong-key, wrong-claim, and wrong-scope credentials |
| Observability tests | Bounded metrics and non-disclosing events |
| Compose validation | Exact secret mounts and `/run/secrets` paths |
| Runtime isolation | Each container receives only its authorized key files |
| Distributed smoke tests | Authenticated requests succeed in both directions |
| Negative tests | Missing, retired, and insufficient credentials are rejected |

The GitHub Actions workflow executes the quality suites before
the Compose runtime gate. Compose logs are printed after a
failure, and the CI stack is removed unconditionally.

## Review conclusion

The reviewed system provides bidirectional asymmetric service
authentication and scope-based service authorization with
explicit key ownership, fail-closed verification, bounded
observability, and automated regression protection.

The implementation is suitable as a local-development and
portfolio demonstration of distributed authentication. A
production deployment must additionally provide managed
secret distribution, encrypted transport, operational key
rotation procedures, and an incident-response process.
