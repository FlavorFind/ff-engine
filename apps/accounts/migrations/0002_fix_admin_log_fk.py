"""
Fix django_admin_log user_id foreign key.

On the staging DB, admin.0001_initial ran before accounts.0001_initial,
so django_admin_log.user_id was created pointing to auth_user instead of
accounts_customuser. This migration drops the wrong FK and adds the correct one.

Safe to run on any environment — checks whether the wrong constraint exists
before trying to drop it.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
        ("admin", "0003_logentry_add_action_flag_choices"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            DO $$
            BEGIN
                -- Drop the wrong FK that points to auth_user (may not exist on clean installs)
                IF EXISTS (
                    SELECT 1
                    FROM information_schema.table_constraints
                    WHERE constraint_name = 'django_admin_log_user_id_c564eba6_fk_auth_user_id'
                      AND table_name = 'django_admin_log'
                ) THEN
                    ALTER TABLE django_admin_log
                        DROP CONSTRAINT django_admin_log_user_id_c564eba6_fk_auth_user_id;
                END IF;

                -- Add the correct FK pointing to accounts_customuser
                IF NOT EXISTS (
                    SELECT 1
                    FROM information_schema.table_constraints
                    WHERE constraint_name = 'django_admin_log_user_id_fk_accounts_customuser_id'
                      AND table_name = 'django_admin_log'
                ) THEN
                    ALTER TABLE django_admin_log
                        ADD CONSTRAINT django_admin_log_user_id_fk_accounts_customuser_id
                        FOREIGN KEY (user_id)
                        REFERENCES accounts_customuser(id)
                        DEFERRABLE INITIALLY DEFERRED;
                END IF;
            END $$;
            """,
            reverse_sql="""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM information_schema.table_constraints
                    WHERE constraint_name = 'django_admin_log_user_id_fk_accounts_customuser_id'
                      AND table_name = 'django_admin_log'
                ) THEN
                    ALTER TABLE django_admin_log
                        DROP CONSTRAINT django_admin_log_user_id_fk_accounts_customuser_id;
                END IF;
            END $$;
            """,
        ),
    ]
