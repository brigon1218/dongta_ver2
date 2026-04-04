# Migration to rename payment tables to Django ORM naming convention

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('payment', '0002_alter_paymenthistory_options_and_more'),
    ]

    operations = [
        # Rename PaymentHistory to payment_paymenthistory
        migrations.RunSQL(
            sql='ALTER TABLE "PaymentHistory" RENAME TO "payment_paymenthistory"',
            reverse_sql='ALTER TABLE "payment_paymenthistory" RENAME TO "PaymentHistory"',
        ),
        # Rename PointAccount to payment_pointaccount
        migrations.RunSQL(
            sql='ALTER TABLE "PointAccount" RENAME TO "payment_pointaccount"',
            reverse_sql='ALTER TABLE "payment_pointaccount" RENAME TO "PointAccount"',
        ),
        # Rename indexes
        migrations.RunSQL(
            sql="""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'member_idx') THEN
                    ALTER INDEX "member_idx" RENAME TO "payment_pointaccount_member_idx";
                END IF;
                IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'member_created_idx') THEN
                    ALTER INDEX "member_created_idx" RENAME TO "payment_paymenthistory_member_created_idx";
                END IF;
                IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'danal_order_id_idx') THEN
                    ALTER INDEX "danal_order_id_idx" RENAME TO "payment_paymenthistory_danal_order_idx";
                END IF;
                IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'tid_idx') THEN
                    ALTER INDEX "tid_idx" RENAME TO "payment_paymenthistory_tid_idx";
                END IF;
                IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'status_idx') THEN
                    ALTER INDEX "status_idx" RENAME TO "payment_paymenthistory_status_idx";
                END IF;
            END $$;
            """,
            reverse_sql='SELECT 1',  # Skip reverse for index renames
        ),
    ]
