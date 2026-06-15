# Generated migration for organizer field and removing is_free index

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0004_add_ticket_tiers'),
        ('organizers', '0001_initial'),
    ]

    operations = [
        # Remove the is_free index first
        migrations.RemoveIndex(
            model_name='event',
            name='events_even_is_free_5e8c44_idx',
        ),
        # Add organizer field
        migrations.AddField(
            model_name='event',
            name='organizer',
            field=models.ForeignKey(
                help_text='Event organizer (cannot delete organizer with events)',
                on_delete=django.db.models.deletion.PROTECT,
                related_name='events',
                to='organizers.organizerprofile',
                null=True,  # Allow null temporarily for migration
            ),
        ),
    ]
