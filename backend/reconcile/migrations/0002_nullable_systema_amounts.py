from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reconcile", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="systemarecord",
            name="base_value",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=15, null=True),
        ),
        migrations.AlterField(
            model_name="systemarecord",
            name="adjustment",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=15, null=True),
        ),
        migrations.AlterField(
            model_name="systemarecord",
            name="total_value",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=15, null=True),
        ),
    ]
