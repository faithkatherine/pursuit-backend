import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Add category FK to Interest model. This is the only migration that
    actually modifies the database (adds a category_id column).
    """

    dependencies = [
        ("core", "0002_interest"),
        ("users", "0008_move_interest_to_core"),
    ]

    operations = [
        migrations.AddField(
            model_name="interest",
            name="category",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="interests",
                to="core.category",
            ),
        ),
    ]
