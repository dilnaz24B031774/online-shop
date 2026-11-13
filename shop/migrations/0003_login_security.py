from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("shop", "0002_product_brand_image")]

    operations = [
        migrations.CreateModel(
            name="LoginSecurityState",
            fields=[
                ("key", models.CharField(max_length=64, primary_key=True, serialize=False)),
                ("scope", models.CharField(max_length=20)),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("window_started_at", models.DateTimeField()),
                ("locked_until", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True, db_index=True)),
            ],
            options={"db_table": "login_security_state", "verbose_name": "защита входа", "verbose_name_plural": "защита входа"},
        ),
        migrations.CreateModel(
            name="LoginChallenge",
            fields=[
                ("id", models.CharField(max_length=64, primary_key=True, serialize=False)),
                ("source_key", models.CharField(max_length=64)),
                ("purpose", models.CharField(max_length=20)),
                ("answer_digest", models.CharField(max_length=64)),
                ("expires_at", models.DateTimeField(db_index=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"db_table": "login_challenges"},
        ),
    ]
