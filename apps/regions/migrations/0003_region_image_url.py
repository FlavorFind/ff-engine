"""
Add image_url field to Region model.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("regions", "0002_remove_dishregion_unique_dish_region_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="region",
            name="image_url",
            field=models.URLField(
                blank=True,
                default="",
                max_length=500,
                help_text="Cloudinary CDN URL for the region hero image (ff/region/{slug}/hero). Set via FFCC Image Studio.",
            ),
        ),
    ]
