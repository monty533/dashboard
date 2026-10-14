from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('db_structure', '0104_rename_userdetails_holder_type'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=[
                        'ALTER TABLE `userdetails` ADD COLUMN `cdsl_push_at_datetime` DATETIME NULL',
                        "UPDATE `userdetails` SET `cdsl_push_at_datetime` = CURRENT_TIMESTAMP WHERE `cdsl_push_at` = 1",
                        'ALTER TABLE `userdetails` DROP COLUMN `cdsl_push_at`',
                        'ALTER TABLE `userdetails` CHANGE COLUMN `cdsl_push_at_datetime` `cdsl_push_at` DATETIME NULL',
                    ],
                    reverse_sql=[
                        'ALTER TABLE `userdetails` ADD COLUMN `cdsl_push_at_boolean` TINYINT(1) NOT NULL DEFAULT 0',
                        "UPDATE `userdetails` SET `cdsl_push_at_boolean` = 1 WHERE `cdsl_push_at` IS NOT NULL",
                        'ALTER TABLE `userdetails` DROP COLUMN `cdsl_push_at`',
                        'ALTER TABLE `userdetails` CHANGE COLUMN `cdsl_push_at_boolean` `cdsl_push_at` TINYINT(1) NOT NULL DEFAULT 0',
                    ],
                ),
            ],
            state_operations=[
                migrations.AlterField(
                    model_name='userdetails',
                    name='cdsl_push_at',
                    field=models.DateTimeField(
                        blank=True,
                        db_column='cdsl_push_at',
                        null=True,
                    ),
                ),
            ],
        ),
    ]
