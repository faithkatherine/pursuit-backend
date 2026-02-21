import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    """Move Interest model into core app state without touching the database.

    The actual table (users_interests) already exists and stays in place.
    """

    dependencies = [
        ("core", "0001_initial"),
        ("users", "0007_userprofile_allow_location_sharing"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name="Interest",
                    fields=[
                        (
                            "id",
                            models.UUIDField(
                                default=uuid.uuid4,
                                editable=False,
                                primary_key=True,
                                serialize=False,
                            ),
                        ),
                        ("name", models.CharField(max_length=100, unique=True)),
                        ("description", models.TextField(blank=True)),
                        (
                            "icon",
                            models.CharField(blank=True, max_length=50, null=True),
                        ),
                    ],
                    options={
                        "verbose_name": "Interest",
                        "verbose_name_plural": "Interests",
                        "db_table": "users_interests",
                        "ordering": ["name"],
                        "indexes": [
                            models.Index(
                                fields=["name"],
                                name="users_inter_name_172fbf_idx",
                            ),
                        ],
                    },
                ),
            ],
            database_operations=[],
        ),
    ]
