from __future__ import annotations

import re
from typing import Any

from backend.app.config import get_settings


class TraefikConfigError(ValueError):
    pass


def _router_token(service_slug: str) -> str:
    token = re.sub(r"[^a-z0-9-]", "-", service_slug.lower())
    return token.strip("-") or "service"


def _is_local_domain(domain: str) -> bool:
    return domain == "localhost" or domain.endswith(".localhost")


def _get_target_port(ports: list[dict[str, Any]]) -> int:
    for port in ports:
        container_port = port.get("container_port")
        if container_port is not None:
            return int(container_port)
    raise TraefikConfigError("Services with a domain must expose at least one container port")


def build_traefik_labels(service_slug: str, domain: str, ports: list[dict[str, Any]]) -> dict[str, str]:
    settings = get_settings()
    target_port = _get_target_port(ports)
    token = _router_token(service_slug)
    service_name = f"{token}-svc"
    http_router = f"{token}-http"
    https_router = f"{token}-https"
    redirect_middleware = f"{token}-redirect"
    host_rule = f"Host(`{domain}`)"

    labels = {
        "traefik.enable": "true",
        "traefik.docker.network": settings.traefik_public_network,
        f"traefik.http.services.{service_name}.loadbalancer.server.port": str(target_port),
        f"traefik.http.routers.{http_router}.rule": host_rule,
        f"traefik.http.routers.{http_router}.entrypoints": settings.traefik_web_entrypoint,
        f"traefik.http.routers.{https_router}.rule": host_rule,
        f"traefik.http.routers.{https_router}.entrypoints": settings.traefik_websecure_entrypoint,
        f"traefik.http.routers.{https_router}.service": service_name,
        f"traefik.http.routers.{https_router}.tls": "true",
    }

    if _is_local_domain(domain):
        labels[f"traefik.http.routers.{http_router}.service"] = service_name
    else:
        labels[f"traefik.http.routers.{http_router}.middlewares"] = redirect_middleware
        labels[f"traefik.http.middlewares.{redirect_middleware}.redirectscheme.scheme"] = "https"
        labels[f"traefik.http.middlewares.{redirect_middleware}.redirectscheme.permanent"] = "true"
        labels[f"traefik.http.routers.{https_router}.tls.certresolver"] = settings.traefik_cert_resolver

    return labels


def build_service_routing(
    *,
    service_slug: str,
    domain: str | None,
    ports: list[dict[str, Any]],
    requested_network: str | None,
    base_labels: dict[str, str] | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    labels = dict(base_labels or {})
    primary_network = requested_network
    extra_networks: list[str] = []

    if domain:
        labels.update(build_traefik_labels(service_slug=service_slug, domain=domain, ports=ports))
        if requested_network and requested_network != settings.traefik_public_network:
            extra_networks.append(settings.traefik_public_network)
        else:
            primary_network = settings.traefik_public_network

    return {
        "labels": labels,
        "network": primary_network,
        "extra_networks": extra_networks,
    }


__all__ = [
    "TraefikConfigError",
    "build_service_routing",
    "build_traefik_labels",
]
