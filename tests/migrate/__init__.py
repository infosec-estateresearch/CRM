"""crm-migrate tests (CRM-002). No network, no loopback, no Docker, no root.

Run from the repository root:
    python3 -I -B -m unittest discover -s tests/migrate -t . -v
"""

import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MIGRATE = os.path.join(REPO, "migrate")
LIB = os.path.join(MIGRATE, "lib")
CONTRACT_PATH = os.path.join(MIGRATE, "contract", "salesforce-fields.json")
COMPOSE_PATH = os.path.join(REPO, "deploy", "migrate", "compose.json")
ENV_EXAMPLE_PATH = os.path.join(REPO, "deploy", "migrate", "env.example")
SCRIPT_PATH = os.path.join(REPO, "scripts", "migrate.sh")
REGISTER_PATH = os.path.join(REPO, "security", "EXTERNAL_CODE_REGISTER.yaml")
DOC_PATH = os.path.join(REPO, "docs", "MIGRATION.md")

if LIB not in sys.path:
    sys.path.insert(0, LIB)
