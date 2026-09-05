from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.domain.incident import (
    Incident,
    IncidentSeverity,
    IncidentStatus,
)
from app.models.incident import IncidentModel


class SqlAlchemyIncidentRepository:
    def __init__(
        self,
        session: Session,
    ) -> None:
        self._session = session

    def list(
    self,
    *,
    search: str | None = None,
    service_id: UUID | None = None,
    severity: IncidentSeverity | None = None,
    status: IncidentStatus | None = None,
    offset: int = 0,
    limit: int = 50,
    ) -> list[Incident]:
        statement = (
            select(IncidentModel)
            .order_by(
                IncidentModel.created_at.desc()
            )
            .offset(offset)
            .limit(limit)
        )

        if search:
            pattern = f"%{search.strip()}%"

            statement = statement.where(
                or_(
                    IncidentModel.title.ilike(pattern),
                    IncidentModel.summary.ilike(pattern),
                    IncidentModel.assignee.ilike(pattern),
                )
            )

        if service_id is not None:
            statement = statement.where(
                IncidentModel.service_id
                == service_id
            )

        if severity is not None:
            statement = statement.where(
                IncidentModel.severity
                == severity
            )

        if status is not None:
            statement = statement.where(
                IncidentModel.status
                == status
            )

        models = self._session.scalars(
            statement
        ).all()

        return [
            self._to_domain(model)
            for model in models
        ]

    def get_by_id(
        self,
        incident_id: UUID,
    ) -> Incident | None:
        model = self._find_model(
            incident_id
        )

        if model is None:
            return None

        return self._to_domain(
            model
        )

    def create(
        self,
        incident: Incident,
    ) -> Incident:
        model = self._to_model(
            incident
        )

        self._session.add(
            model
        )

        self._session.flush()

        return self._to_domain(
            model
        )

    def update(
        self,
        incident: Incident,
    ) -> Incident:
        model = self._find_model(
            incident.id
        )

        if model is None:
            raise LookupError(
                f"Incident {incident.id} "
                "does not exist."
            )

        model.title = incident.title
        model.service_id = incident.service_id
        model.severity = incident.severity
        model.status = incident.status
        model.summary = incident.summary
        model.assignee = incident.assignee
        model.started_at = incident.started_at
        model.resolved_at = incident.resolved_at
        model.created_at = incident.created_at
        model.updated_at = incident.updated_at

        self._session.flush()

        return self._to_domain(
            model
        )

    def delete(
        self,
        incident_id: UUID,
    ) -> None:
        model = self._find_model(
            incident_id
        )

        if model is None:
            return

        self._session.delete(
            model
        )

        self._session.flush()

    def _find_model(
        self,
        incident_id: UUID,
    ) -> IncidentModel | None:
        statement = (
            select(IncidentModel)
            .where(
                IncidentModel.id
                == incident_id
            )
        )

        return self._session.scalar(
            statement
        )

    @staticmethod
    def _to_model(
        incident: Incident,
    ) -> IncidentModel:
        return IncidentModel(
            id=incident.id,
            service_id=incident.service_id,
            title=incident.title,
            severity=incident.severity,
            status=incident.status,
            summary=incident.summary,
            assignee=incident.assignee,
            started_at=incident.started_at,
            resolved_at=incident.resolved_at,
            created_at=incident.created_at,
            updated_at=incident.updated_at,
        )

    @staticmethod
    def _to_domain(
        model: IncidentModel,
    ) -> Incident:
        return Incident(
            id=model.id,
            service_id=model.service_id,
            title=model.title,
            severity=model.severity,
            status=model.status,
            summary=model.summary,
            assignee=model.assignee,
            started_at=model.started_at,
            resolved_at=model.resolved_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )