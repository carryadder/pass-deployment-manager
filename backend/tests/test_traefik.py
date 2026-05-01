from backend.app.config import get_settings
from backend.app.core.traefik import build_service_routing, build_traefik_labels


def test_build_traefik_labels_for_real_domain_includes_tls_resolver() -> None:
    labels = build_traefik_labels(
        service_slug="hello-world",
        domain="hello.example.com",
        ports=[{"container_port": 8080}],
    )
    settings = get_settings()

    assert labels["traefik.enable"] == "true"
    assert labels["traefik.docker.network"] == settings.traefik_public_network
    assert labels["traefik.http.routers.hello-world-https.tls"] == "true"
    assert (
        labels["traefik.http.routers.hello-world-https.tls.certresolver"]
        == settings.traefik_cert_resolver
    )
    assert labels["traefik.http.services.hello-world-svc.loadbalancer.server.port"] == "8080"


def test_build_service_routing_attaches_public_network_as_extra_network() -> None:
    settings = get_settings()

    routing = build_service_routing(
        service_slug="hello-world",
        domain="hello.example.com",
        ports=[{"container_port": 8080}],
        requested_network="private-stack",
        base_labels={"dmgr.service.slug": "hello-world"},
    )

    assert routing["network"] == "private-stack"
    assert routing["extra_networks"] == [settings.traefik_public_network]
    assert routing["labels"]["dmgr.service.slug"] == "hello-world"


def test_build_traefik_labels_for_localhost_skips_acme_resolver() -> None:
    labels = build_traefik_labels(
        service_slug="hello-world",
        domain="hello.localhost",
        ports=[{"container_port": 3000}],
    )

    assert "traefik.http.routers.hello-world-https.tls.certresolver" not in labels
    assert labels["traefik.http.routers.hello-world-http.service"] == "hello-world-svc"
