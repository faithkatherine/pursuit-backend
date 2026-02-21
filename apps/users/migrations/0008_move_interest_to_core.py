from django.db import migrations, models


class Migration(migrations.Migration):
    """Remove Interest from users app state and point M2M to core.Interest.

    No database operations — the table and M2M through table stay in place.
    """

    dependencies = [
        ("core", "0002_interest"),
        ("users", "0007_userprofile_allow_location_sharing"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name="Interest"),
            ],
            database_operations=[],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name="userprofile",
                    name="interests",
                    field=models.ManyToManyField(
                        blank=True,
                        help_text="User's selected interests for personalization",
                        related_name="users",
                        to="core.interest",
                    ),
                ),
            ],
            database_operations=[],
        ),
    ]
