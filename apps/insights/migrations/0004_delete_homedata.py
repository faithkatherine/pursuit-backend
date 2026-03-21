from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("insights", "0003_add_icon_to_weatherdata"),
    ]

    operations = [
        migrations.DeleteModel(
            name="HomeData",
        ),
    ]
