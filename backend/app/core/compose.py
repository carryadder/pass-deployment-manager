"""docker-compose.yml parser.

We support the subset of the v3 spec that maps cleanly onto our service
model: image, environment, ports, volumes, networks, restart, healthcheck,
and deploy.resources.limits.cpus / memory. Build directives, depends_on
ordering, configs, and secrets are flagged but not enforced.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import yaml


class ComposeParseError(Exception):
    """Raised when a compose document cannot be parsed into our service model."""


@dataclass
class ParsedPort:
    container_port: int
    host_port: int | None = None


@dataclass
class ParsedVolume:
    source: str
    target: str
    mode: str = "rw"


@dataclass
class ParsedHealthcheck:
    type: str
    value: str
    interval_seconds: int = 10
    timeout_seconds: int = 3
    start_period_seconds: int = 5
    retries: int = 3


@dataclass
class ParsedBuild:
    context: str = "."
    dockerfile: str | None = None
    args: dict[str, str] = field(default_factory=dict)


@dataclass
class ParsedService:
    name: str
    image: str
    cpus: float
    memory_mb: int
    env: dict[str, str] = field(default_factory=dict)
    ports: list[ParsedPort] = field(default_factory=list)
    volumes: list[ParsedVolume] = field(default_factory=list)
    network: str | None = None
    domain: str | None = None
    restart_policy: str = "unless-stopped"
    pids_limit: int | None = 256
    healthcheck: ParsedHealthcheck | None = None
    build: ParsedBuild | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass
class ParsedCompose:
    services: list[ParsedService]
    declared_volumes: list[str]
    declared_networks: list[str]
    warnings: list[str]


_MEMORY_PATTERN = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([kKmMgGtT]?)([bB]?)\s*$")


def _parse_memory_to_mb(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        # raw bytes
        return max(1, int(float(value) / (1024 * 1024)))
    if not isinstance(value, str):
        return None
    match = _MEMORY_PATTERN.match(value)
    if not match:
        return None
    amount = float(match.group(1))
    unit = match.group(2).lower()
    multiplier = {
        "": 1,
        "k": 1 / 1024,  # KB -> MB
        "m": 1,
        "g": 1024,
        "t": 1024 * 1024,
    }.get(unit, 1)
    return max(1, int(amount * multiplier))


def _parse_cpus(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _parse_environment(raw: Any) -> dict[str, str]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return {str(k): "" if v is None else str(v) for k, v in raw.items()}
    if isinstance(raw, list):
        result: dict[str, str] = {}
        for item in raw:
            if not isinstance(item, str):
                continue
            if "=" in item:
                key, value = item.split("=", 1)
                result[key.strip()] = value
            else:
                result[item.strip()] = ""
        return result
    return {}


def _parse_ports(raw: Any) -> list[ParsedPort]:
    if not raw:
        return []
    ports: list[ParsedPort] = []
    for entry in raw:
        if isinstance(entry, dict):
            target = entry.get("target")
            published = entry.get("published")
            if target is None:
                continue
            ports.append(
                ParsedPort(
                    container_port=int(target),
                    host_port=int(published) if published is not None else None,
                )
            )
            continue
        if isinstance(entry, int):
            ports.append(ParsedPort(container_port=int(entry)))
            continue
        if not isinstance(entry, str):
            continue
        # Strip protocol suffix like "/tcp"
        candidate = entry.split("/")[0]
        # Forms: "8080:80", "127.0.0.1:8080:80", "80", "8080-8090:8080-8090" (range, unsupported)
        if "-" in candidate:
            # range — pick the first port and warn upstream (caller adds warning)
            candidate = candidate.split("-", 1)[0]
        chunks = candidate.split(":")
        try:
            if len(chunks) == 1:
                ports.append(ParsedPort(container_port=int(chunks[0])))
            elif len(chunks) == 2:
                ports.append(
                    ParsedPort(container_port=int(chunks[1]), host_port=int(chunks[0]))
                )
            elif len(chunks) >= 3:
                # ip:host:container
                ports.append(
                    ParsedPort(container_port=int(chunks[2]), host_port=int(chunks[1]))
                )
        except ValueError:
            continue
    return ports


def _parse_volumes(raw: Any, declared_volumes: set[str]) -> tuple[list[ParsedVolume], list[str]]:
    if not raw:
        return [], []
    volumes: list[ParsedVolume] = []
    warnings: list[str] = []
    for entry in raw:
        if isinstance(entry, dict):
            source = entry.get("source")
            target = entry.get("target")
            mode = "ro" if entry.get("read_only") else "rw"
            if not source or not target:
                continue
            if entry.get("type") == "bind":
                warnings.append(f"Bind mount {source} -> {target} skipped; only named volumes are supported.")
                continue
            volumes.append(ParsedVolume(source=str(source), target=str(target), mode=mode))
            continue
        if not isinstance(entry, str):
            continue
        chunks = entry.split(":")
        if len(chunks) < 2:
            continue
        source, target = chunks[0], chunks[1]
        mode = "ro" if len(chunks) >= 3 and "ro" in chunks[2] else "rw"
        if source.startswith(".") or source.startswith("/"):
            warnings.append(f"Bind mount {source} -> {target} skipped; only named volumes are supported.")
            continue
        if declared_volumes and source not in declared_volumes:
            warnings.append(f"Volume '{source}' is not declared in the top-level volumes block.")
        volumes.append(ParsedVolume(source=source, target=target, mode=mode))
    return volumes, warnings


def _parse_restart(raw: Any) -> str:
    mapping = {
        None: "unless-stopped",
        "no": "no",
        "always": "always",
        "unless-stopped": "unless-stopped",
        "on-failure": "on-failure",
    }
    value = raw if isinstance(raw, str) else None
    return mapping.get(value, "unless-stopped")


def _parse_healthcheck(raw: Any) -> ParsedHealthcheck | None:
    if not isinstance(raw, dict):
        return None
    if raw.get("disable"):
        return None
    test = raw.get("test")
    if not test:
        return None

    if isinstance(test, list):
        if not test:
            return None
        first = test[0]
        if first in {"CMD", "CMD-SHELL"}:
            command = " ".join(str(part) for part in test[1:]) if len(test) > 1 else ""
            if not command:
                return None
            value = command
            kind = "cmd"
        else:
            value = " ".join(str(part) for part in test)
            kind = "cmd"
    else:
        value = str(test)
        kind = "cmd"

    def _seconds(name: str, default: int) -> int:
        candidate = raw.get(name)
        if isinstance(candidate, str) and candidate.endswith("s"):
            try:
                return int(float(candidate[:-1]))
            except ValueError:
                return default
        if isinstance(candidate, (int, float)):
            return int(candidate)
        return default

    return ParsedHealthcheck(
        type=kind,
        value=value,
        interval_seconds=_seconds("interval", 10),
        timeout_seconds=_seconds("timeout", 3),
        start_period_seconds=_seconds("start_period", 5),
        retries=int(raw.get("retries", 3)),
    )


def _parse_build(raw: Any) -> ParsedBuild | None:
    if raw is None:
        return None
    if isinstance(raw, str):
        return ParsedBuild(context=raw)
    if not isinstance(raw, dict):
        return None
    context = raw.get("context")
    dockerfile = raw.get("dockerfile")
    build_args = raw.get("args")
    if not isinstance(context, str) or not context.strip():
        context = "."
    if dockerfile is not None and not isinstance(dockerfile, str):
        dockerfile = None
    args: dict[str, str] = {}
    if isinstance(build_args, dict):
        args = {str(key): "" if value is None else str(value) for key, value in build_args.items()}
    return ParsedBuild(context=context.strip(), dockerfile=dockerfile.strip() if isinstance(dockerfile, str) else None, args=args)


def _parse_service(
    name: str,
    raw: dict[str, Any],
    declared_volumes: set[str],
    allow_build: bool,
) -> ParsedService:
    warnings: list[str] = []
    build = _parse_build(raw.get("build"))
    if build is not None and "image" not in raw and not allow_build:
        raise ComposeParseError(
            f"Service '{name}' uses a build directive. Compose import requires a prebuilt image."
        )
    image = raw.get("image")
    if build is not None and (not isinstance(image, str) or not image.strip()):
        image = f"build:{build.context}"
        warnings.append(f"Service '{name}' will be built from the repository using context '{build.context}'.")
    if not isinstance(image, str) or not image.strip():
        raise ComposeParseError(f"Service '{name}' is missing an image.")

    # deploy.resources.limits.cpus / memory take precedence
    deploy = raw.get("deploy") or {}
    resources = (deploy.get("resources") or {}).get("limits") or {}
    cpus = _parse_cpus(resources.get("cpus")) or _parse_cpus(raw.get("cpus")) or 0.5
    memory_mb = (
        _parse_memory_to_mb(resources.get("memory"))
        or _parse_memory_to_mb(raw.get("mem_limit"))
        or 256
    )

    networks = raw.get("networks")
    network: str | None = None
    if isinstance(networks, list) and networks:
        first = networks[0]
        network = first if isinstance(first, str) else None
    elif isinstance(networks, dict) and networks:
        network = next(iter(networks.keys()))

    parsed_volumes, volume_warnings = _parse_volumes(raw.get("volumes"), declared_volumes)
    warnings.extend(volume_warnings)

    if "depends_on" in raw:
        warnings.append(
            f"Service '{name}': depends_on ordering is not enforced — start order may differ."
        )
    if "configs" in raw or "secrets" in raw:
        warnings.append(f"Service '{name}': configs / secrets are not imported.")

    return ParsedService(
        name=name,
        image=image.strip(),
        cpus=cpus,
        memory_mb=memory_mb,
        env=_parse_environment(raw.get("environment")),
        ports=_parse_ports(raw.get("ports")),
        volumes=parsed_volumes,
        network=network,
        domain=None,
        restart_policy=_parse_restart(raw.get("restart")),
        pids_limit=int(raw["pids_limit"]) if isinstance(raw.get("pids_limit"), int) else 256,
        healthcheck=_parse_healthcheck(raw.get("healthcheck")),
        build=build,
        warnings=warnings,
    )


def parse_compose(yaml_text: str, allow_build: bool = False) -> ParsedCompose:
    if not yaml_text or not yaml_text.strip():
        raise ComposeParseError("Compose document is empty.")
    try:
        document = yaml.safe_load(yaml_text)
    except yaml.YAMLError as exc:
        raise ComposeParseError(f"Invalid YAML: {exc}") from exc
    if not isinstance(document, dict):
        raise ComposeParseError("Compose document must be a mapping at the top level.")

    services_block = document.get("services")
    if not isinstance(services_block, dict) or not services_block:
        raise ComposeParseError("Compose document has no services.")

    declared_volumes_block = document.get("volumes") or {}
    declared_volumes = set(declared_volumes_block.keys()) if isinstance(declared_volumes_block, dict) else set()
    declared_networks_block = document.get("networks") or {}
    declared_networks = (
        list(declared_networks_block.keys()) if isinstance(declared_networks_block, dict) else []
    )

    services: list[ParsedService] = []
    document_warnings: list[str] = []
    for name, service_raw in services_block.items():
        if not isinstance(service_raw, dict):
            document_warnings.append(f"Service '{name}' is not a mapping; skipped.")
            continue
        services.append(_parse_service(str(name), service_raw, declared_volumes, allow_build))

    return ParsedCompose(
        services=services,
        declared_volumes=sorted(declared_volumes),
        declared_networks=declared_networks,
        warnings=document_warnings,
    )


__all__ = [
    "ComposeParseError",
    "ParsedCompose",
    "ParsedBuild",
    "ParsedHealthcheck",
    "ParsedPort",
    "ParsedService",
    "ParsedVolume",
    "parse_compose",
]
