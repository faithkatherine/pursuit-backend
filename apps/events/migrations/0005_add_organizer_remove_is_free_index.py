# Generated migration for organizer field compatibility.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0004_add_ticket_tiers'),
        ('organizers', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='event',
            name='organizer',
            field=models.ForeignKey(
                help_text='Event organizer (cannot delete organizer with events)',
                on_delete=django.db.models.deletion.PROTECT,
                related_name='events',
                to='organizers.organizerprofile',
                null=True,
            ),
        ),
    ]
