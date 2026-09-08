from __future__ import annotations

import ast

from dataclasses import (
    dataclass,
)

from pathlib import (
    Path,
)

from types import (
    ModuleType,
)

import app.api.dependencies as dependency_module

import app.api.routes.auth as auth_route_module


# =========================================================
# EVENT REQUIREMENT MODEL
# =========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class EventRequirement:
    """
    Describe one security-event contract that must exist
    inside an authentication function.

    Optional fields let each requirement assert only the
    metadata relevant to that particular event.
    """

    event: str

    outcome: str | None = None

    reason: str | None = None

    requires_request: bool = True

    requires_user_id: bool = False

    requires_account_identifier: bool = False

    required_detail_keys: tuple[
        str,
        ...,
    ] = ()


# =========================================================
# DISCOVERED EVENT MODEL
# =========================================================


@dataclass(
    frozen=True,
    slots=True,
)
class DiscoveredEvent:
    """
    One security_event_logger.emit(...) call discovered in
    application source.
    """

    function_name: str

    event: str | None

    outcome: str | None

    reason: str | None

    keyword_names: frozenset[
        str
    ]

    detail_keys: frozenset[
        str
    ]


# =========================================================
# SOURCE HELPERS
# =========================================================


def module_source_path(
    module: ModuleType,
) -> Path:
    """
    Return the source file for an imported application
    module.
    """

    module_file = (
        module.__file__
    )

    assert (
        module_file
        is not None
    )

    path = (
        Path(
            module_file
        )
        .resolve()
    )

    assert (
        path.is_file()
    )

    return (
        path
    )


def parse_module(
    module: ModuleType,
) -> ast.Module:
    """
    Parse the real application source into a Python AST.
    """

    path = (
        module_source_path(
            module
        )
    )

    source = (
        path.read_text(
            encoding="utf-8"
        )
    )

    return (
        ast.parse(
            source,
            filename=str(
                path
            ),
        )
    )


# =========================================================
# AST VALUE HELPERS
# =========================================================


def literal_string(
    node: ast.AST | None,
) -> str | None:
    """
    Return a literal string value when the AST node contains
    one.

    Dynamic expressions intentionally return None.
    """

    if (
        isinstance(
            node,
            ast.Constant,
        )
        and isinstance(
            node.value,
            str,
        )
    ):
        return (
            node.value
        )

    return (
        None
    )


def keyword_mapping(
    call: ast.Call,
) -> dict[
    str,
    ast.AST,
]:
    """
    Convert ordinary named call arguments into a lookup map.

    **kwargs expansions are ignored because the current
    security-event contract intentionally uses explicit
    keyword arguments.
    """

    result: dict[
        str,
        ast.AST,
    ] = {}

    for keyword in (
        call.keywords
    ):
        if (
            keyword.arg
            is None
        ):
            continue

        result[
            keyword.arg
        ] = (
            keyword.value
        )

    return (
        result
    )


def detail_keys_from_node(
    node: ast.AST | None,
) -> frozenset[
    str
]:
    """
    Extract literal keys from a details={...} mapping.

    Values are deliberately ignored.
    """

    if not isinstance(
        node,
        ast.Dict,
    ):
        return (
            frozenset()
        )

    keys: set[
        str
    ] = set()

    for key_node in (
        node.keys
    ):
        key = (
            literal_string(
                key_node
            )
            if key_node
            is not None
            else None
        )

        if (
            key
            is not None
        ):
            keys.add(
                key
            )

    return (
        frozenset(
            keys
        )
    )


# =========================================================
# LOGGER CALL IDENTIFICATION
# =========================================================


def is_security_event_emit_call(
    node: ast.Call,
) -> bool:
    """
    Match:

        security_event_logger.emit(...)
    """

    function = (
        node.func
    )

    return (
        isinstance(
            function,
            ast.Attribute,
        )
        and function.attr
        == "emit"
        and isinstance(
            function.value,
            ast.Name,
        )
        and function.value.id
        == "security_event_logger"
    )


# =========================================================
# EVENT EXTRACTION
# =========================================================


def discover_security_events(
    module: ModuleType,
) -> list[
    DiscoveredEvent
]:
    """
    Discover every security_event_logger.emit() call in the
    supplied module and associate it with its containing
    function.
    """

    tree = (
        parse_module(
            module
        )
    )

    discovered: list[
        DiscoveredEvent
    ] = []

    for node in (
        tree.body
    ):
        if not isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        ):
            continue

        function_name = (
            node.name
        )

        for nested_node in (
            ast.walk(
                node
            )
        ):
            if not isinstance(
                nested_node,
                ast.Call,
            ):
                continue

            if not (
                is_security_event_emit_call(
                    nested_node
                )
            ):
                continue

            keywords = (
                keyword_mapping(
                    nested_node
                )
            )

            discovered.append(
                DiscoveredEvent(
                    function_name=(
                        function_name
                    ),
                    event=(
                        literal_string(
                            keywords.get(
                                "event"
                            )
                        )
                    ),
                    outcome=(
                        literal_string(
                            keywords.get(
                                "outcome"
                            )
                        )
                    ),
                    reason=(
                        literal_string(
                            keywords.get(
                                "reason"
                            )
                        )
                    ),
                    keyword_names=(
                        frozenset(
                            keywords.keys()
                        )
                    ),
                    detail_keys=(
                        detail_keys_from_node(
                            keywords.get(
                                "details"
                            )
                        )
                    ),
                )
            )

    return (
        discovered
    )


# =========================================================
# REQUIREMENT MATCHING
# =========================================================


def event_matches_requirement(
    event: DiscoveredEvent,
    requirement: EventRequirement,
) -> bool:
    if (
        event.event
        != requirement.event
    ):
        return (
            False
        )

    if (
        requirement.outcome
        is not None
        and event.outcome
        != requirement.outcome
    ):
        return (
            False
        )

    if (
        requirement.reason
        is not None
        and event.reason
        != requirement.reason
    ):
        return (
            False
        )

    if (
        requirement.requires_request
        and "request"
        not in event.keyword_names
    ):
        return (
            False
        )

    if (
        requirement.requires_user_id
        and "user_id"
        not in event.keyword_names
    ):
        return (
            False
        )

    if (
        requirement
        .requires_account_identifier
        and "account_identifier"
        not in event.keyword_names
    ):
        return (
            False
        )

    if not (
        set(
            requirement
            .required_detail_keys
        )
        .issubset(
            event.detail_keys
        )
    ):
        return (
            False
        )

    return (
        True
    )


def require_function_events(
    discovered: list[
        DiscoveredEvent
    ],
    *,
    function_name: str,
    requirements: tuple[
        EventRequirement,
        ...,
    ],
) -> None:
    """
    Assert that a function contains every required audit
    event.
    """

    function_events = [
        event
        for event
        in discovered
        if (
            event.function_name
            == function_name
        )
    ]

    assert (
        function_events
    ), (
        f"No security events were discovered in "
        f"{function_name!r}."
    )

    for requirement in (
        requirements
    ):
        matches = [
            event
            for event
            in function_events
            if (
                event_matches_requirement(
                    event,
                    requirement,
                )
            )
        ]

        assert (
            matches
        ), (
            "Missing authentication security-event "
            f"contract in {function_name!r}: "
            f"{requirement!r}. "
            f"Discovered events: "
            f"{function_events!r}"
        )


# =========================================================
# LOGIN AUDIT COVERAGE
# =========================================================


def test_login_has_success_failure_and_throttle_audit_events(
) -> None:
    discovered = (
        discover_security_events(
            auth_route_module
        )
    )

    require_function_events(
        discovered,
        function_name=(
            "login_for_access_token"
        ),
        requirements=(
            EventRequirement(
                event=(
                    "auth.login.throttled"
                ),
                outcome=(
                    "blocked"
                ),
                requires_account_identifier=(
                    True
                ),
            ),
            EventRequirement(
                event=(
                    "auth.login.failed"
                ),
                outcome=(
                    "failure"
                ),
                reason=(
                    "invalid_credentials"
                ),
                requires_account_identifier=(
                    True
                ),
            ),
            EventRequirement(
                event=(
                    "auth.login.succeeded"
                ),
                outcome=(
                    "success"
                ),
                requires_user_id=(
                    True
                ),
            ),
        ),
    )


# =========================================================
# REAUTHENTICATION AUDIT COVERAGE
# =========================================================


def test_reauthentication_has_success_and_failure_audit_events(
) -> None:
    discovered = (
        discover_security_events(
            auth_route_module
        )
    )

    require_function_events(
        discovered,
        function_name=(
            "reauthenticate_current_user"
        ),
        requirements=(
            EventRequirement(
                event=(
                    "auth.reauthentication.failed"
                ),
                outcome=(
                    "failure"
                ),
                reason=(
                    "invalid_current_password"
                ),
                requires_user_id=(
                    True
                ),
            ),
            EventRequirement(
                event=(
                    "auth.reauthentication.succeeded"
                ),
                outcome=(
                    "success"
                ),
                requires_user_id=(
                    True
                ),
            ),
        ),
    )


# =========================================================
# PASSWORD CHANGE AUDIT COVERAGE
# =========================================================


def test_password_change_has_complete_audit_events(
) -> None:
    discovered = (
        discover_security_events(
            auth_route_module
        )
    )

    require_function_events(
        discovered,
        function_name=(
            "change_current_user_password"
        ),
        requirements=(
            EventRequirement(
                event=(
                    "auth.password_change.blocked"
                ),
                outcome=(
                    "blocked"
                ),
                reason=(
                    "invalid_or_stale_reauthentication"
                ),
                requires_user_id=(
                    True
                ),
            ),
            EventRequirement(
                event=(
                    "auth.password_change.failed"
                ),
                outcome=(
                    "failure"
                ),
                reason=(
                    "password_policy_rejected"
                ),
                requires_user_id=(
                    True
                ),
            ),
            EventRequirement(
                event=(
                    "auth.password_change.succeeded"
                ),
                outcome=(
                    "success"
                ),
                requires_user_id=(
                    True
                ),
                required_detail_keys=(
                    "sessions_revoked",
                ),
            ),
        ),
    )


# =========================================================
# PASSWORD RESET REQUEST AUDIT COVERAGE
# =========================================================


def test_password_reset_request_has_complete_audit_events(
) -> None:
    discovered = (
        discover_security_events(
            auth_route_module
        )
    )

    require_function_events(
        discovered,
        function_name=(
            "request_password_reset"
        ),
        requirements=(
            EventRequirement(
                event=(
                    "auth.password_reset.throttled"
                ),
                outcome=(
                    "blocked"
                ),
                requires_account_identifier=(
                    True
                ),
                required_detail_keys=(
                    "retry_after_seconds",
                ),
            ),
            EventRequirement(
                event=(
                    "auth.password_reset.delivery_failed"
                ),
                outcome=(
                    "failure"
                ),
                reason=(
                    "delivery_provider_failure"
                ),
                requires_user_id=(
                    True
                ),
            ),
            EventRequirement(
                event=(
                    "auth.password_reset.requested"
                ),
                outcome=(
                    "success"
                ),
                requires_account_identifier=(
                    True
                ),
            ),
        ),
    )


# =========================================================
# PASSWORD RESET CONFIRMATION AUDIT COVERAGE
# =========================================================


def test_password_reset_confirmation_has_complete_audit_events(
) -> None:
    discovered = (
        discover_security_events(
            auth_route_module
        )
    )

    require_function_events(
        discovered,
        function_name=(
            "confirm_password_reset"
        ),
        requirements=(
            EventRequirement(
                event=(
                    "auth.password_reset.failed"
                ),
                outcome=(
                    "failure"
                ),
                reason=(
                    "invalid_or_expired_reset_credential"
                ),
            ),
            EventRequirement(
                event=(
                    "auth.password_reset.failed"
                ),
                outcome=(
                    "failure"
                ),
                reason=(
                    "replacement_password_rejected"
                ),
            ),
            EventRequirement(
                event=(
                    "auth.password_reset.completed"
                ),
                outcome=(
                    "success"
                ),
                requires_user_id=(
                    True
                ),
                required_detail_keys=(
                    "sessions_revoked",
                ),
            ),
        ),
    )


# =========================================================
# REFRESH AUDIT COVERAGE
# =========================================================


def test_refresh_has_complete_audit_events(
) -> None:
    discovered = (
        discover_security_events(
            auth_route_module
        )
    )

    require_function_events(
        discovered,
        function_name=(
            "refresh_access_token"
        ),
        requirements=(
            EventRequirement(
                event=(
                    "auth.refresh.failed"
                ),
                outcome=(
                    "failure"
                ),
                reason=(
                    "missing_refresh_cookie"
                ),
            ),
            EventRequirement(
                event=(
                    "csrf.validation.failed"
                ),
                outcome=(
                    "blocked"
                ),
                reason=(
                    "refresh_request"
                ),
            ),
            EventRequirement(
                event=(
                    "auth.refresh.reuse_detected"
                ),
                outcome=(
                    "blocked"
                ),
                reason=(
                    "refresh_token_reuse"
                ),
                requires_user_id=(
                    True
                ),
            ),
            EventRequirement(
                event=(
                    "auth.refresh.failed"
                ),
                outcome=(
                    "failure"
                ),
                reason=(
                    "invalid_refresh_credential"
                ),
            ),
            EventRequirement(
                event=(
                    "auth.refresh.succeeded"
                ),
                outcome=(
                    "success"
                ),
                requires_user_id=(
                    True
                ),
                required_detail_keys=(
                    "refresh_rotated",
                ),
            ),
        ),
    )


# =========================================================
# LOGOUT AUDIT COVERAGE
# =========================================================


def test_logout_has_security_relevant_audit_events(
) -> None:
    """
    Missing-cookie logout remains an intentionally idempotent
    no-op and is therefore not required to generate a
    security event.

    Actual successful revocation, CSRF rejection, and refresh
    reuse remain auditable.
    """

    discovered = (
        discover_security_events(
            auth_route_module
        )
    )

    require_function_events(
        discovered,
        function_name=(
            "logout"
        ),
        requirements=(
            EventRequirement(
                event=(
                    "csrf.validation.failed"
                ),
                outcome=(
                    "blocked"
                ),
                reason=(
                    "logout_request"
                ),
            ),
            EventRequirement(
                event=(
                    "auth.logout.reuse_detected"
                ),
                outcome=(
                    "blocked"
                ),
                reason=(
                    "refresh_token_reuse"
                ),
                requires_user_id=(
                    True
                ),
            ),
            EventRequirement(
                event=(
                    "auth.logout.succeeded"
                ),
                outcome=(
                    "success"
                ),
                requires_user_id=(
                    True
                ),
                required_detail_keys=(
                    "session_revoked",
                ),
            ),
        ),
    )


# =========================================================
# LOGOUT-ALL AUDIT COVERAGE
# =========================================================


def test_logout_all_has_revocation_audit_event(
) -> None:
    discovered = (
        discover_security_events(
            auth_route_module
        )
    )

    require_function_events(
        discovered,
        function_name=(
            "logout_all"
        ),
        requirements=(
            EventRequirement(
                event=(
                    "auth.logout_all.succeeded"
                ),
                outcome=(
                    "success"
                ),
                requires_user_id=(
                    True
                ),
                required_detail_keys=(
                    "sessions_revoked",
                ),
            ),
        ),
    )


# =========================================================
# ACCESS TOKEN AUDIT COVERAGE
# =========================================================


def test_invalid_access_token_has_dependency_level_audit_event(
) -> None:
    """
    Access-token rejection occurs inside get_current_user()
    rather than inside the /me route itself.
    """

    discovered = (
        discover_security_events(
            dependency_module
        )
    )

    require_function_events(
        discovered,
        function_name=(
            "get_current_user"
        ),
        requirements=(
            EventRequirement(
                event=(
                    "auth.access_token.failed"
                ),
                outcome=(
                    "failure"
                ),
                reason=(
                    "invalid_access_token"
                ),
            ),
        ),
    )


# =========================================================
# REQUEST CONTEXT CONTRACT
# =========================================================


def test_auth_route_security_events_include_request_context(
) -> None:
    """
    Every auth-route security event should provide the logger
    with the Request object so it can safely record:

        method
        route path
        server-established client address

    without recording headers, query strings, or bodies.
    """

    discovered = (
        discover_security_events(
            auth_route_module
        )
    )

    assert (
        discovered
    )

    missing_request = [
        event
        for event
        in discovered
        if (
            "request"
            not in event.keyword_names
        )
    ]

    assert (
        missing_request
        == []
    ), (
        "Authentication security events without request "
        f"context were found: {missing_request!r}"
    )