from sqlalchemy.orm import configure_mappers

from backend.app.models import AuditLog, Deploy, EnvVar, Project, Secret, Service, User


def test_model_exports_are_available() -> None:
    assert User.__tablename__ == "users"
    assert Project.__tablename__ == "projects"
    assert Service.__tablename__ == "services"
    assert Deploy.__tablename__ == "deploys"
    assert EnvVar.__tablename__ == "env_vars"
    assert Secret.__tablename__ == "secrets"
    assert AuditLog.__tablename__ == "audit_logs"


def test_timestamp_columns_are_distinct_per_table() -> None:
    project_created_at = Project.__table__.c.created_at
    service_created_at = Service.__table__.c.created_at

    assert project_created_at is not service_created_at
    assert project_created_at.table.name == "projects"
    assert service_created_at.table.name == "services"


def test_mappers_configure_successfully() -> None:
    configure_mappers()

    assert AuditLog.actor.property.mapper.class_ is User
