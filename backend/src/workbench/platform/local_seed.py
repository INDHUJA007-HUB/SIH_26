"""Idempotently seed the synthetic local database and object-store buckets."""

import json

from workbench.platform.config import Settings
from workbench.tools import seed_buckets, seed_database


def main() -> None:
    settings = Settings()
    result = {
        "database": seed_database(settings),
        "storage": seed_buckets(settings),
        "synthetic": True,
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
