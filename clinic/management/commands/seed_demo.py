"""Creates demo doctors, a demo patient and sample appointments for trying the portal locally.

Never run this against a production database: it creates accounts with well-known passwords.
"""
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import PatientProfile
from clinic import services
from clinic.models import Appointment, Department, Doctor, DoctorSchedule

DOCTOR_PASSWORD = "Doctor@2026"
PATIENT_EMAIL = "patient@bsu.demo"
PATIENT_PASSWORD = "Patient@2026"

DOCTORS = [
    # first, last, department title, specialty, slot minutes
    ("Amina", "Yusuf", "General Medicine", "Family medicine", 20),
    ("Emmanuel", "Tor", "Internal Medicine", "Diabetes and hypertension", 30),
    ("Grace", "Ortom", "Gynaecology", "Antenatal and women's health", 20),
    ("Samuel", "Adoga", "Eye Care Centre", "Ophthalmology", 15),
    ("Ruth", "Iorhemen", "Children Health Care Centre", "Paediatrics", 20),
    ("Daniel", "Kwaghe", "Cardiology", "Preventive cardiology", 30),
]


def next_weekday(start):
    day = start
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return day


def previous_weekday(start):
    day = start
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day


class Command(BaseCommand):
    help = "Create demo doctors, a demo patient and sample appointments."

    @transaction.atomic
    def handle(self, *args, **options):
        doctors = []
        for first, last, dept_title, specialty, slot_minutes in DOCTORS:
            email = f"{first}.{last}@bsu.demo".lower()
            user, created = User.objects.get_or_create(
                username=email, defaults={"email": email, "first_name": first, "last_name": last}
            )
            if created:
                user.set_password(DOCTOR_PASSWORD)
                user.save()
            department = Department.objects.get(title=dept_title)
            doctor, _ = Doctor.objects.get_or_create(
                user=user,
                defaults={
                    "department": department,
                    "specialty": specialty,
                    "slot_minutes": slot_minutes,
                    "bio": f"{specialty} consultant at BSU Medical Centre.",
                },
            )
            if not doctor.schedules.exists():
                for weekday in range(5):  # Monday to Friday
                    DoctorSchedule.objects.create(doctor=doctor, weekday=weekday, start_time="09:00", end_time="13:00")
                    DoctorSchedule.objects.create(doctor=doctor, weekday=weekday, start_time="14:00", end_time="16:00")
                if first in ("Amina", "Ruth"):
                    DoctorSchedule.objects.create(doctor=doctor, weekday=5, start_time="09:00", end_time="12:00")
            doctors.append(doctor)

        patient, created = User.objects.get_or_create(
            username=PATIENT_EMAIL,
            defaults={"email": PATIENT_EMAIL, "first_name": "Demo", "last_name": "Patient"},
        )
        if created:
            patient.set_password(PATIENT_PASSWORD)
            patient.save()
        PatientProfile.objects.get_or_create(user=patient, defaults={"phone": "08012345678", "gender": "F"})

        if not Appointment.objects.filter(patient=patient).exists():
            today = timezone.localdate()
            upcoming_day = next_weekday(today + timedelta(days=1))
            slots = services.get_available_slots(doctors[0], upcoming_day)
            if slots:
                services.book_appointment(
                    patient=patient, doctor=doctors[0], day=upcoming_day, start=slots[0],
                    reason="Persistent cough and mild fever for three days.",
                )
            past_day = previous_weekday(today - timedelta(days=1))
            Appointment.objects.create(
                patient=patient, patient_name=services.full_name(patient), doctor=doctors[1],
                date=past_day, start_time="10:00", end_time="10:30",
                reason="Routine blood pressure and sugar check.",
                status=Appointment.Status.COMPLETED, rating=5,
                feedback="Very thorough and patient. Clear explanation of my results.",
                doctor_notes="BP within target. Repeat fasting glucose in 3 months.",
            )

        self.stdout.write(self.style.SUCCESS("Demo data ready."))
        self.stdout.write("Doctor accounts (password: %s):" % DOCTOR_PASSWORD)
        for doctor in doctors:
            self.stdout.write(f"  {doctor.user.email}  ·  {doctor.display_name} ({doctor.department.title})")
        self.stdout.write(f"Patient account: {PATIENT_EMAIL} (password: {PATIENT_PASSWORD})")
        self.stdout.write("Staff/admin: create one with  python manage.py createsuperuser")
