from django.core.management.base import BaseCommand

from clinic.services import send_due_reminders


class Command(BaseCommand):
    help = "Notify patients (in-app and by e-mail) about appointments happening tomorrow. Safe to run repeatedly."

    def handle(self, *args, **options):
        sent = send_due_reminders()
        self.stdout.write(self.style.SUCCESS(f"Sent {sent} reminder(s)."))
