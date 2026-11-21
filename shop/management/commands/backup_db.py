from django.core.management.base import BaseCommand, CommandError

from shop.backups import KEEP, create_backup, list_backups


class Command(BaseCommand):
    help = "Save a backup copy of the database to the folder backups/ (keeps the last 10)"

    def add_arguments(self, parser):
        parser.add_argument("--keep", type=int, default=KEEP, help="how many newest copies to keep")
        parser.add_argument("--json", action="store_true", help="save data as JSON instead of pg_dump")
        parser.add_argument("--list", action="store_true", help="only show the saved copies")

    def handle(self, *args, **opts):
        if opts["list"]:
            for p in list_backups():
                self.stdout.write(f"{p.name}  {p.stat().st_size / 1024:.0f} KB")
            return
        try:
            path = create_backup(keep=opts["keep"], force_json=opts["json"])
        except RuntimeError as e:
            raise CommandError(f"Backup failed: {e}")
        self.stdout.write(self.style.SUCCESS(f"Saved: backups/{path.name} ({path.stat().st_size / 1024:.0f} KB)"))
