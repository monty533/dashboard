from django.db import migrations


def ensure_nse_support(apps, schema_editor):
    connection = schema_editor.connection

    if connection.vendor == "mysql":
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS `nse_credentials` (
                    `id` bigint NOT NULL AUTO_INCREMENT,
                    `username` varchar(50) NULL,
                    `password` varchar(50) NULL,
                    `apiName` varchar(50) NULL,
                    `created_at` datetime(6) NOT NULL,
                    `updated_at` datetime(6) NOT NULL,
                    `user_id` int NULL,
                    PRIMARY KEY (`id`),
                    UNIQUE KEY `nse_credentials_user_id_unique` (`user_id`),
                    KEY `nse_credentials_user_id_idx` (`user_id`),
                    CONSTRAINT `nse_credentials_user_id_fk`
                        FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`)
                        ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )

    state_master = apps.get_model("db_structure", "NseStateCodeMaster")
    state_master.objects.using(connection.alias).update_or_create(
        state_name="apo",
        defaults={"state_code": "98"},
    )


class Migration(migrations.Migration):
    dependencies = [("db_structure", "0003_seed_nse_state_codes")]

    operations = [migrations.RunPython(ensure_nse_support, migrations.RunPython.noop)]
