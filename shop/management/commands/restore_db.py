from django.core.management.base import BaseCommand, CommandError

from shop.backups import create_backup, get_backup, list_backups, restore_backup


class Command(BaseCommand):
    help = "Restore the database from a copy in backups/ (the newest one if no name is given)"

    def add_arguments(self, parser):
        parser.add_argument("name", nargs="?", help="file name, e.g. sauda_2026-11-21_10-00-00.sql")
        parser.add_argument("--yes", action="store_true", help="really replace the current data")

    def handle(self, *args, **opts):
        files = list_backups()
        if not files:
            raise CommandError("No backups yet. Make one: python manage.py backup_db")
        path = get_backup(opts["name"]) if opts["name"] else files[0]
        if not path:
            raise CommandError("No such file in backups/. See: python manage.py backup_db --list")
        if not opts["yes"]:
            self.stdout.write(self.style.WARNING(
                f"This replaces the current data with {path.name}.\n"
                f"Run again with --yes:  python manage.py restore_db {path.name} --yes"))
            return
        safety = create_backup()          # current state first, in case the wrong file was chosen
        try:
            restore_backup(path)
        except RuntimeError as e:
            raise CommandError(f"Restore failed: {e}")
        self.stdout.write(self.style.SUCCESS(
            f"Restored from {path.name}. The data before restoring is saved in {safety.name}."))
