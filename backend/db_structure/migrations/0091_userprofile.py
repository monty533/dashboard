from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def create_existing_profiles(apps, schema_editor):
    user_model = apps.get_model(settings.AUTH_USER_MODEL.split('.', 1)[0], settings.AUTH_USER_MODEL.split('.', 1)[1])
    profile_model = apps.get_model('db_structure', 'UserProfile')
    profile_model.objects.using(schema_editor.connection.alias).bulk_create(
        [profile_model(user_id=user.pk) for user in user_model.objects.using(schema_editor.connection.alias).all()],
        ignore_conflicts=True,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('db_structure', '0090_alter_nsdlaccounttypemaster_id_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='UserProfile',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                ('company_name', models.CharField(blank=True, default='', max_length=255)),
                ('phone', models.CharField(blank=True, default='', max_length=20)),
                ('address', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'user',
                    models.OneToOneField(
                        db_column='user_id',
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='profile',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={'db_table': 'user_profiles'},
        ),
        migrations.RunPython(create_existing_profiles, migrations.RunPython.noop),
    ]
