from backend.app.core.metrics import parse_container_stats, parse_metrics_range


def test_parse_metrics_range_supports_minutes_and_hours() -> None:
    assert int(parse_metrics_range("5m").total_seconds()) == 300
    assert int(parse_metrics_range("1h").total_seconds()) == 3600


def test_parse_container_stats_extracts_expected_fields() -> None:
    stats = {
        "cpu_stats": {
            "cpu_usage": {"total_usage": 400},
            "system_cpu_usage": 2000,
            "online_cpus": 2,
        },
        "precpu_stats": {
            "cpu_usage": {"total_usage": 200},
            "system_cpu_usage": 1000,
        },
        "memory_stats": {"usage": 256, "limit": 1024},
        "networks": {
            "eth0": {"rx_bytes": 100, "tx_bytes": 50},
            "eth1": {"rx_bytes": 25, "tx_bytes": 75},
        },
        "blkio_stats": {
            "io_service_bytes_recursive": [
                {"op": "Read", "value": 10},
                {"op": "Write", "value": 20},
            ]
        },
        "pids_stats": {"current": 4},
    }

    parsed = parse_container_stats(stats)

    assert parsed["cpu_percent"] == 40.0
    assert parsed["memory_percent"] == 25.0
    assert parsed["network_rx_bytes"] == 125
    assert parsed["network_tx_bytes"] == 125
    assert parsed["block_read_bytes"] == 10
    assert parsed["block_write_bytes"] == 20
    assert parsed["pids"] == 4
    assert "timestamp" in parsed
