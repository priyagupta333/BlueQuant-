from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0009_purchase_certificate"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE api_purchase
            ADD COLUMN IF NOT EXISTS certificate varchar(100);
            """,
            reverse_sql="""
            ALTER TABLE api_purchase
            DROP COLUMN IF EXISTS certificate;
            """,
        ),
    ]
