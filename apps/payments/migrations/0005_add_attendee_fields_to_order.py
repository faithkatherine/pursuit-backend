# Generated migration for attendee fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0004_add_order_items'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='attendee_name',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='order',
            name='attendee_email',
            field=models.EmailField(blank=True, max_length=254),
        ),
    ]
