from backend.app.core.runner import build_run_config


def test_build_run_config_translates_resource_limits() -> None:
    payload = {
        "name": "demo-service",
        "image": "nginx:latest",
        "cpus": 0.5,
        "memory_mb": 512,
        "disk_mb": 1024,
        "env": {"APP_ENV": "production"},
        "ports": [{"container_port": 80, "host_port": 8080}],
        "volumes": [{"source": "demo-data", "target": "/data", "mode": "rw"}],
        "network": "demo-network",
        "restart_policy": "unless-stopped",
        "labels": {"dmgr.service.slug": "demo-service"},
        "pids_limit": 200,
    }

    result = build_run_config(payload)

    assert result["nano_cpus"] == 500000000
    assert result["mem_limit"] == 512 * 1024 * 1024
    assert result["storage_opt"] == {"size": "1024m"}
    assert result["ports"] == {"80": 8080}
    assert result["volumes"] == {"demo-data": {"bind": "/data", "mode": "rw"}}
    assert result["network"] == "demo-network"
    assert result["environment"] == {"APP_ENV": "production"}
    assert result["restart_policy"] == {"Name": "unless-stopped"}
    assert result["pids_limit"] == 200
