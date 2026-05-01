from __future__ import annotations

import hashlib
import hmac
import json
import secrets as secrets_module
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from sqlmodel import select
from starlette.concurrency import run_in_threadpool

from backend.app.db import session_scope
from backend.app.models.audit_log import AuditLog
from backend.app.models.deploy import Deploy
from backend.app.models.service import Service
from backend.app.workers.tasks import enqueue_deploy_job

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


PROVIDER_GITHUB = "github"
PROVIDER_GITLAB = "gitlab"
PROVIDER_GITEA = "gitea"
PROVIDER_GENERIC = "generic"


def detect_provider(headers: dict[str, str]) -> str:
    if "x-github-event" in headers or "x-hub-signature-256" in headers:
        return PROVIDER_GITHUB
    if "x-gitea-event" in headers or "x-gitea-signature" in headers:
        return PROVIDER_GITEA
    if "x-gitlab-event" in headers or "x-gitlab-token" in headers:
        return PROVIDER_GITLAB
    return PROVIDER_GENERIC


def _constant_time_eq(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def _verify_hmac_sha256(secret: str, body: bytes, header_value: str | None, prefix: str = "sha256=") -> bool:
    if not header_value:
        return False
    expected = "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    received = header_value.strip()
    if not received.startswith(prefix):
        # Gitea sends raw hex, no prefix
        if prefix == "sha256=":
            received = "sha256=" + received
    return _constant_time_eq(received, expected)


def verify_signature(provider: str, secret: str, body: bytes, headers: dict[str, str]) -> bool:
    if provider == PROVIDER_GITHUB:
        return _verify_hmac_sha256(secret, body, headers.get("x-hub-signature-256"))
    if provider == PROVIDER_GITEA:
        # Gitea sends the raw hex digest in X-Gitea-Signature.
        return _verify_hmac_sha256(secret, body, headers.get("x-gitea-signature"))
    if provider == PROVIDER_GITLAB:
        # GitLab sends the configured token verbatim.
        token = headers.get("x-gitlab-token")
        if token is None:
            return False
        return _constant_time_eq(token, secret)
    # Generic providers: require an X-Webhook-Token header equal to the secret.
    token = headers.get("x-webhook-token")
    if token is None:
        return False
    return _constant_time_eq(token, secret)


def extract_ref_and_commit(provider: str, payload: dict[str, Any]) -> tuple[str | None, str | None]:
    if provider in (PROVIDER_GITHUB, PROVIDER_GITEA, PROVIDER_GITLAB, PROVIDER_GENERIC):
        ref = payload.get("ref")
        commit = payload.get("after") or payload.get("checkout_sha")
        if not commit and isinstance(payload.get("head_commit"), dict):
            commit = payload["head_commit"].get("id")
        return ref, commit
    return None, None


def ref_matches_branch(ref: str | None, branch: str | None) -> bool:
    if not branch:
        return True
    if not ref:
        return False
    return ref == branch or ref == f"refs/heads/{branch}"


def generate_token() -> str:
    return secrets_module.token_urlsafe(24)


def generate_secret() -> str:
    return secrets_module.token_urlsafe(32)


def _find_service_by_token_sync(token: str) -> Service | None:
    with session_scope() as session:
        statement = select(Service)
        services = session.exec(statement).all()
        for service in services:
            webhook = (service.config or {}).get("webhook") or {}
            if webhook.get("token") and _constant_time_eq(webhook["token"], token):
                # Detach from session by re-fetching the row id; we'll reopen as needed
                session.expunge(service)
                return service
        return None


def _queue_redeploy_sync(service_id: UUID, ref: str | None, commit: str | None, provider: str) -> UUID | None:
    with session_scope() as session:
        service = session.get(Service, service_id)
        if service is None:
            return None
        webhook = (service.config or {}).get("webhook") or {}
        git_url = webhook.get("git_url")
        if not git_url:
            return None
        branch = webhook.get("branch")
        dockerfile_path = webhook.get("dockerfile_path")
        build_args = webhook.get("build_args") or {}

        deploy = Deploy(
            service_id=service.id,
            status="queued",
            source_type="webhook",
            source_ref=ref or git_url,
        )
        session.add(deploy)
        service.status = "build_queued"
        session.add(service)
        session.add(
            AuditLog(
                actor_id=None,
                action="service.webhook.received",
                resource_type="service",
                resource_id=str(service.id),
                details={
                    "provider": provider,
                    "ref": ref,
                    "commit": commit,
                    "deploy_id": None,
                },
            )
        )
        session.commit()
        session.refresh(deploy)

        enqueue_deploy_job(
            deploy_id=deploy.id,
            service_id=service.id,
            git_url=git_url,
            branch=branch,
            commit=commit,
            dockerfile_path=dockerfile_path,
            build_args=build_args,
        )
        return deploy.id


@router.post("/{token}", status_code=status.HTTP_202_ACCEPTED)
async def receive_webhook(token: str, request: Request) -> dict:
    body = await request.body()
    headers = {key.lower(): value for key, value in request.headers.items()}
    provider = detect_provider(headers)

    service = await run_in_threadpool(_find_service_by_token_sync, token)
    if service is None:
        # Avoid leaking which tokens exist; return generic 404.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")

    webhook_config = (service.config or {}).get("webhook") or {}
    if not webhook_config.get("enabled", True):
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Webhook is disabled")

    secret = webhook_config.get("secret")
    if not secret:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Webhook secret is not configured")

    if not verify_signature(provider, secret, body, headers):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook signature")

    # GitHub sends a ping when the hook is created — acknowledge without queuing.
    github_event = headers.get("x-github-event")
    gitea_event = headers.get("x-gitea-event")
    gitlab_event = headers.get("x-gitlab-event")
    if github_event == "ping" or gitea_event == "ping":
        return {"ok": True, "event": "ping", "provider": provider}

    if github_event and github_event != "push":
        return {"ok": True, "event": github_event, "provider": provider, "ignored": True}
    if gitea_event and gitea_event != "push":
        return {"ok": True, "event": gitea_event, "provider": provider, "ignored": True}
    if gitlab_event and gitlab_event.lower() not in {"push hook", "push"}:
        return {"ok": True, "event": gitlab_event, "provider": provider, "ignored": True}

    try:
        payload: dict[str, Any] = json.loads(body) if body else {}
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON payload") from exc

    ref, commit = extract_ref_and_commit(provider, payload)
    branch = webhook_config.get("branch")
    if not ref_matches_branch(ref, branch):
        return {
            "ok": True,
            "event": github_event or gitea_event or gitlab_event or "push",
            "provider": provider,
            "ignored": True,
            "reason": f"ref {ref} does not match configured branch {branch}",
        }

    deploy_id = await run_in_threadpool(_queue_redeploy_sync, service.id, ref, commit, provider)
    if deploy_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Webhook is configured but the service has no git source; configure git_url first.",
        )

    return {
        "ok": True,
        "provider": provider,
        "event": "push",
        "ref": ref,
        "commit": commit,
        "deploy_id": str(deploy_id),
    }
