from backend.app.models import AuditLog, Deploy, EnvVar, Project, Secret, Service, User


def test_model_exports_are_available() -> None:
    assert User.__tablename__ == "users"
    assert Project.__tablename__ == "projects"
    assert Service.__tablename__ == "services"
    assert Deploy.__tablename__ == "deploys"
    assert EnvVar.__tablename__ == "env_vars"
    assert Secret.__tablename__ == "secrets"
    assert AuditLog.__tablename__ == "audit_logs"
