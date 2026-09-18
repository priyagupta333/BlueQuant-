from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0013_fieldofficerlogin_isroadminlogin'),
    ]

    operations = [
        migrations.CreateModel(
            name='TenderV2',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tender_title', models.CharField(max_length=255)),
                ('required_credits', models.IntegerField()),
                ('location_preference', models.CharField(blank=True, max_length=255)),
                ('deadline', models.DateField(blank=True, null=True)),
                ('budget_range', models.CharField(blank=True, max_length=255)),
                ('description', models.TextField(blank=True)),
                ('status', models.CharField(choices=[('Open', 'Open'), ('Under Review', 'Under Review'), ('Closed', 'Closed')], default='Open', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('corporate', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tenders_v2', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='ProposalV2',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('offered_credits', models.IntegerField()),
                ('price_per_credit', models.DecimalField(decimal_places=2, max_digits=10)),
                ('project_location', models.CharField(max_length=255)),
                ('supporting_documents', models.FileField(blank=True, null=True, upload_to='tenders/proposals/')),
                ('project_description', models.TextField(blank=True)),
                ('status', models.CharField(choices=[('Pending', 'Pending'), ('Accepted', 'Accepted'), ('Rejected', 'Rejected')], default='Pending', max_length=16)),
                ('chain_tx_hash', models.CharField(blank=True, max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('contributor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='proposals_v2', to=settings.AUTH_USER_MODEL)),
                ('tender', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='proposals', to='api.tenderv2')),
            ],
        ),
    ]
