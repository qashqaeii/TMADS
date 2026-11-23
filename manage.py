#!/usr/bin/env python
import os
import sys


def main() -> None:
    from config.django_settings import apply_django_settings_module

    apply_django_settings_module()
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Install dependencies from requirements.txt."
        ) from exc
    if len(sys.argv) > 1 and sys.argv[1] in {"runserver", "collectstatic"}:
        from scripts.optimize_landing_assets import optimize

        from scripts.optimize_features_assets import optimize as optimize_features

        optimize()
        optimize_features()
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
