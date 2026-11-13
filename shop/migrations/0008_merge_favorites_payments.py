# Joins Dilyara's favorites (0003_favorite) with Dilnaz's branch (... 0007_qr_installment).
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("shop", "0003_favorite"),
        ("shop", "0007_qr_installment"),
    ]
    operations = []
