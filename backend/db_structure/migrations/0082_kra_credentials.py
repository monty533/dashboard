from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("db_structure", "0081_ckyc_credentials"),
    ]

    operations = [
        migrations.CreateModel(
            name="KraCredentials",
            fields=[
                ("id", models.BigAutoField(db_column="id", primary_key=True, serialize=False)),
                ("environment", models.CharField(default="uat", max_length=10)),
                ("token_url", models.CharField(blank=True, default="", max_length=255)),
                ("pan_status_url", models.CharField(blank=True, default="", max_length=255)),
                ("fetch_data_url", models.CharField(blank=True, default="", max_length=255)),
                ("insert_data_url", models.CharField(blank=True, default="", max_length=255)),
                ("api_key", models.CharField(blank=True, default="", max_length=255)),
                ("username", models.CharField(blank=True, default="", max_length=100)),
                ("poscode", models.CharField(blank=True, default="", max_length=50)),
                ("cvlkra_password", models.CharField(blank=True, default="", max_length=255)),
                ("aes_key", models.CharField(blank=True, default="", max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.ForeignKey(
                    db_column="user_id",
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="kra_credentials",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                "db_table": "kra_credentials",
                "unique_together": {( "user", "environment")},
            },
        ),
    ]
