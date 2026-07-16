"""Built-in default configuration (lowest-precedence tier, TDD §20).

similarity_tolerance_default has no value specified anywhere in the
frozen docs; 0.95 is a first-draft engineering default (same status as
the repair loop's other first-draft constants) — revisit once Sprint
10's real repair loop produces measurements.
"""

DEFAULTS: dict = {
    "api": {
        "bind_host": "127.0.0.1",  # never 0.0.0.0 — v3 §17.2
        "port": 8781,
        "auth_token_path": "./.pms/auth_token",
    },
    "data": {
        "sqlite_path": "./.pms/data/pms.sqlite3",
        "backup_dir": "./.pms/backups",
    },
    "logging": {
        "level": "INFO",
        "retention_days": 90,
        "log_dir": "./.pms/logs",
    },
    "pipeline": {
        "repair_max_attempts_default": 3,
        "similarity_tolerance_default": 0.95,
    },
    "plugins": {
        "products_dir": "./products",
    },
}
