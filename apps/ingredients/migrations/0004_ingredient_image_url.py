"""
Add image_url field to Ingredient model.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ingredients", "0003_e59b_staples_audit"),
    ]

    operations = [
        migrations.AddField(
            model_name="ingredient",
            name="image_url",
            field=models.URLField(
                blank=True,
                default="",
                max_length=500,
                help_text="Cloudinary CDN URL for the ingredient image (ff/ingredient/{slug}/default). Set via FFCC Image Studio.",
            ),
        ),
    ]
