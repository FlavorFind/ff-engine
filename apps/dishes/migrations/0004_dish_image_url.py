"""
Add image_url field to Dish model.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("dishes", "0003_dish_trgm_indexes"),
    ]

    operations = [
        migrations.AddField(
            model_name="dish",
            name="image_url",
            field=models.URLField(
                blank=True,
                default="",
                max_length=500,
                help_text="Cloudinary CDN URL for the hero image (ff/dish/{slug}/hero). Set via FFCC Image Studio.",
            ),
        ),
    ]
