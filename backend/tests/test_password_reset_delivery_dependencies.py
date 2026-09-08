from __future__ import (
    annotations,
)

from typing import (
    Any,
)

from fastapi.dependencies.utils import (
    get_dependant,
)

from app.api.dependencies import (
    get_password_reset_delivery,
    get_password_reset_delivery_coordinator,
    get_ses_client,
)

from app.infrastructure.aws.ses_password_reset_delivery import (
    SesPasswordResetDelivery,
)


# =========================================================
# TEST SES CLIENT
# =========================================================


class RecordingSesClient:
    """
    Minimal SES v2 test double.

    The delivery factory only needs an object satisfying the
    SesClient protocol. No AWS credentials or network calls
    are required for this dependency-wiring suite.
    """

    def __init__(
        self,
    ) -> None:
        self.requests: list[
            dict[
                str,
                Any,
            ]
        ] = []

    def send_email(
        self,
        **kwargs: Any,
    ) -> dict[
        str,
        Any,
    ]:
        self.requests.append(
            kwargs
        )

        return {
            "MessageId": (
                "dependency-test-message-id"
            ),
        }


# =========================================================
# FACTORY TEST
# =========================================================


def test_password_reset_delivery_factory_returns_ses_adapter(
) -> None:
    """
    The application's production delivery factory must
    resolve to SES rather than the historical discard
    adapter.
    """

    client = (
        RecordingSesClient()
    )

    delivery = (
        get_password_reset_delivery(
            client
        )
    )

    assert isinstance(
        delivery,
        SesPasswordResetDelivery,
    )


# =========================================================
# COORDINATOR DEPENDENCY GRAPH
# =========================================================


def test_password_reset_coordinator_uses_current_delivery_factory(
) -> None:
    """
    Verify that FastAPI captured the CURRENT
    get_password_reset_delivery function.

    This specifically prevents the following regression:

        1. define discard get_password_reset_delivery
        2. create PasswordResetDeliveryDependency
        3. create coordinator dependency
        4. redefine get_password_reset_delivery as SES

    In that broken arrangement, Python's current function
    name points to SES but the coordinator's Depends object
    still contains the earlier discard function object.
    """

    dependant = (
        get_dependant(
            path=(
                "/dependency-test"
            ),
            call=(
                get_password_reset_delivery_coordinator
            ),
        )
    )

    delivery_dependencies = [
        dependency
        for dependency
        in dependant.dependencies
        if dependency.name
        == "delivery"
    ]

    assert len(
        delivery_dependencies
    ) == 1

    delivery_dependency = (
        delivery_dependencies[
            0
        ]
    )

    assert (
        delivery_dependency.call
        is get_password_reset_delivery
    )


# =========================================================
# SES CLIENT DEPENDENCY GRAPH
# =========================================================


def test_password_reset_delivery_depends_on_ses_client(
) -> None:
    """
    Verify the complete provider-side dependency chain:

        coordinator
            ↓
        delivery factory
            ↓
        SES client factory

    This assertion does not create a boto3 client and does
    not contact AWS. It inspects FastAPI's resolved
    dependency metadata only.
    """

    coordinator_dependant = (
        get_dependant(
            path=(
                "/dependency-test"
            ),
            call=(
                get_password_reset_delivery_coordinator
            ),
        )
    )

    delivery_dependencies = [
        dependency
        for dependency
        in coordinator_dependant.dependencies
        if dependency.name
        == "delivery"
    ]

    assert len(
        delivery_dependencies
    ) == 1

    delivery_dependency = (
        delivery_dependencies[
            0
        ]
    )

    assert (
        delivery_dependency.call
        is get_password_reset_delivery
    )

    ses_dependencies = [
        dependency
        for dependency
        in delivery_dependency.dependencies
        if dependency.name
        == "ses_client"
    ]

    assert len(
        ses_dependencies
    ) == 1

    ses_dependency = (
        ses_dependencies[
            0
        ]
    )

    assert (
        ses_dependency.call
        is get_ses_client
    )


# =========================================================
# GRAPH UNIQUENESS
# =========================================================


def test_password_reset_coordinator_has_one_delivery_dependency(
) -> None:
    """
    The coordinator should have exactly two direct
    dependencies:

        link_builder
        delivery

    There must not be parallel discard and SES delivery
    paths.
    """

    dependant = (
        get_dependant(
            path=(
                "/dependency-test"
            ),
            call=(
                get_password_reset_delivery_coordinator
            ),
        )
    )

    dependency_names = {
        dependency.name
        for dependency
        in dependant.dependencies
    }

    assert dependency_names == {
        "link_builder",
        "delivery",
    }