"""Create a store manager without sending a password through shell arguments."""
import getpass
import sys

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction

from shop.models import User
from shop.roles import sync_role_access


class Command(BaseCommand):
    help = "Создать менеджера магазина с ограниченными рабочими правами."

    def add_arguments(self, parser):
        parser.add_argument("username")
        parser.add_argument("--email", required=True)
        parser.add_argument("--password-stdin", action="store_true", help="Прочитать пароль одной строкой из stdin.")
        parser.add_argument("--update-existing", action="store_true", help="Явно разрешить смену роли и пароля существующей записи.")

    def handle(self, *args, **options):
        username = options["username"].strip()
        if not username:
            raise CommandError("Укажите логин менеджера.")
        if User.objects.filter(username=username).exists() and not options["update_existing"]:
            raise CommandError("Этот логин уже занят. Для явного обновления используйте --update-existing.")
        if options["password_stdin"]:
            password = sys.stdin.readline().rstrip("\r\n")
        else:
            if not sys.stdin.isatty():
                raise CommandError("Для интерактивного ввода нужен Terminal. Для stdin укажите --password-stdin.")
            try:
                password = getpass.getpass("Пароль нового менеджера: ")
                confirmation = getpass.getpass("Повторите пароль: ")
            except (EOFError, KeyboardInterrupt) as error:
                raise CommandError("Ввод пароля отменён.") from error
            if password != confirmation:
                raise CommandError("Пароли не совпадают.")
        try:
            with transaction.atomic():
                user = User.objects.select_for_update().filter(username=username).first()
                if user is not None and not options["update_existing"]:
                    raise CommandError("Этот логин уже занят; существующая запись не изменена.")
                previous_role = user.role if user else None
                if user is None:
                    user = User(username=username, preferred_language=User.Language.RU)
                user.email = User.objects.normalize_email(options["email"].strip())
                user.role = User.Role.MANAGER
                user.is_staff = True
                user.is_superuser = False
                validate_password(password, user)
                user.set_password(password)
                user.full_clean()
                user.save()
                sync_role_access(user, previous_role=previous_role)
        except ValidationError as error:
            raise CommandError(" ".join(error.messages)) from error
        except IntegrityError as error:
            raise CommandError("Логин или email уже занят. Данные не изменены.") from error
        self.stdout.write(self.style.SUCCESS(f"Менеджер «{user.username}» готов. Пароль не выводится и хранится только в виде хеша."))
