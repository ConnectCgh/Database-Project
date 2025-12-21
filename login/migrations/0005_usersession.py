from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("login", "0004_merchant_rating_count_merchant_rating_score_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="UserSession",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "user_type",
                    models.CharField(
                        choices=[
                            ("customer", "顾客"),
                            ("rider", "骑手"),
                            ("merchant", "商家"),
                            ("platform", "平台"),
                        ],
                        max_length=20,
                    ),
                ),
                ("session_token", models.CharField(max_length=64, unique=True)),
                ("user_agent", models.CharField(blank=True, max_length=255, null=True)),
                (
                    "client_ip",
                    models.GenericIPAddressField(blank=True, null=True),
                ),
                ("device_name", models.CharField(blank=True, max_length=120, null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField()),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sessions",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="用户",
                    ),
                ),
            ],
            options={
                "db_table": "user_session",
                "ordering": ["-created_at"],
            },
        ),
    ]
