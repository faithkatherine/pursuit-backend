# Generated migration for Ticket model

import apps.tickets.models
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('organizers', '0001_initial'),
        ('payments', '0005_add_attendee_fields_to_order'),
    ]

    operations = [
        migrations.CreateModel(
            name='Ticket',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.CharField(
                    db_index=True,
                    default=apps.tickets.models.generate_ticket_token,
                    editable=False,
                    max_length=20,
                    unique=True
                )),
                ('attendee_name', models.CharField(
                    blank=True,
                    help_text='Name from checkout user details. Stored at ticket creation time — immutable.',
                    max_length=255
                )),
                ('attendee_email', models.EmailField(
                    blank=True,
                    help_text='Email from checkout user details. Stored at ticket creation time — immutable.',
                    max_length=254
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('used_at', models.DateTimeField(
                    blank=True,
                    help_text='When the ticket was scanned at the door.',
                    null=True
                )),
                ('order_item', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='tickets',
                    to='payments.orderitem'
                )),
                ('used_by', models.ForeignKey(
                    blank=True,
                    help_text='Which organizer scanned this ticket.',
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='scanned_tickets',
                    to='organizers.organizerprofile'
                )),
            ],
            options={
                'db_table': 'tickets_ticket',
                'ordering': ['created_at'],
            },
        ),
    ]
