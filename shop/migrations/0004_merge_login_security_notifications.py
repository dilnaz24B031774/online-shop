# Joins the two branches: login security (my-changes) and notifications (main).
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("shop", "0003_login_security"),
        ("shop", "0003_notification_kind_link"),
    ]
    operations = []
