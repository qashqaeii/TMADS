#!/usr/bin/env python
import os
import sys


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Install dependencies from requirements.txt."
        ) from exc
    if len(sys.argv) > 1 and sys.argv[1] in {"runserver", "collectstatic"}:
        from scripts.optimize_landing_assets import optimize

        optimize()
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
