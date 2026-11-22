from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reconcile", "0002_nullable_systema_amounts"),
    ]

    operations = [
        migrations.CreateModel(
            name="ImportRowError",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("source_file", models.CharField(max_length=200)),
                ("row_number", models.PositiveIntegerField()),
                ("record_id", models.CharField(blank=True, max_length=100)),
                ("raw_row", models.TextField()),
                ("errors", models.TextField()),
            ],
        ),
    ]
