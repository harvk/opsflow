from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.incident import IncidentModel
from app.models.service import ServiceModel

from uuid import uuid4
from sqlalchemy.exc import IntegrityError

import pytest

from tests.constants import PAYMENTS_INCIDENT_ID, PAYMENTS_SERVICE_ID

def test_incident_has_related_service(
    db_session,
    seeded_incidents,
):
    statement = (
        select(IncidentModel)
        .options(selectinload(IncidentModel.service))
        .where(
            IncidentModel.id == PAYMENTS_INCIDENT_ID
        )
    )

    incident = db_session.scalar(statement)

    assert incident is not None
    assert incident.service is not None
    assert incident.service.id == PAYMENTS_SERVICE_ID
    assert incident.service.name == "Payments API"
    
def test_service_has_related_incidents(
    db_session,
    seeded_incidents,
):
    statement = (
        select(ServiceModel)
        .options(selectinload(ServiceModel.incidents))
        .where(
            ServiceModel.id == PAYMENTS_SERVICE_ID
        )
    )

    service = db_session.scalar(statement)

    assert service is not None
    assert len(service.incidents) >= 1

    incident_ids = {
        incident.id
        for incident in service.incidents
    }

    assert PAYMENTS_INCIDENT_ID in incident_ids
    
def test_incident_cannot_reference_missing_service(
    db_session,
):
    with db_session.begin_nested():
        now = datetime.now(
            timezone.utc
        )
        
        incident = IncidentModel(
            id=uuid4(),
            service_id=uuid4(),
            title="Invalid service incident",
            severity="SEV-2",
            status="Open",
            summary="This incident references no real service.",
            assignee="Platform Team",
            source="manual",
            customer_impacting=False,
            acknowledged_at=None,
            started_at=now,
            resolved_at=None,
            created_at=now,
            updated_at=now,
        )
    
        db_session.add(incident)
    
        with pytest.raises(IntegrityError):
            db_session.flush()

    db_session.rollback()
    
def test_deleting_service_deletes_related_incidents(
    db_session,
    seeded_incidents,
):
    incident_before = db_session.get(
        IncidentModel,
        PAYMENTS_INCIDENT_ID,
    )

    assert incident_before is not None

    service = db_session.get(
        ServiceModel,
        PAYMENTS_SERVICE_ID,
    )

    assert service is not None

    db_session.delete(service)
    db_session.flush()

    db_session.expire_all()

    incident_after = db_session.get(
        IncidentModel,
        PAYMENTS_INCIDENT_ID,
    )

    assert incident_after is None