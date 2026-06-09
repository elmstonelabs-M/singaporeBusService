from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_TIMEZONE = "${APP_TIMEZONE:-Asia/Singapore}"


def test_all_compose_services_default_to_singapore_timezone() -> None:
    for filename in ("docker-compose.yml", "docker-compose.prod.yml"):
        compose = yaml.safe_load((PROJECT_ROOT / filename).read_text())

        for service_name, service in compose["services"].items():
            assert service["environment"]["TZ"] == EXPECTED_TIMEZONE, (
                f"{filename} service {service_name} must define the shared timezone"
            )
