import json
from django.core.management.base import BaseCommand, CommandError

from apps.operations.release_checks import readiness_summary


class Command(BaseCommand):
    help = "Read-only production readiness inventory; prints no credentials"

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true", dest="json_output")

    def handle(self, *args, **options):
        result = readiness_summary()
        if options.get("json_output"):
            self.stdout.write(json.dumps({
                "ready": result["ready"],
                "blocked": result["blocked"],
                "pending": result["pending"],
                "can_launch": result["can_launch"],
                "items": [item.as_dict() for item in result["items"]],
            }, ensure_ascii=False))
        else:
            for item in result["items"]:
                self.stdout.write(f"{item.state.upper()}: {item.label} — {item.explanation}")
        if not result["can_launch"]:
            raise CommandError("Production readiness conditions are not verified.")
