from datetime import time, timedelta

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import PatientProfile
from clinic import services
from clinic.models import Appointment, Department, Doctor, DoctorSchedule, mask_name
from clinic.services import BookingError, SlotUnavailable, generate_slot_starts, get_available_slots


def future_weekday(min_days=2):
    day = timezone.localdate() + timedelta(days=min_days)
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return day


class PortalTestCase(TestCase):
    def setUp(self):
        self.dept = Department.objects.get(title="General Medicine")
        self.doc_user = User.objects.create_user(
            "dr.test@bsu.test", "dr.test@bsu.test", "Pass@12345", first_name="Test", last_name="Doctor"
        )
        self.doctor = Doctor.objects.create(user=self.doc_user, department=self.dept, slot_minutes=30)
        for weekday in range(7):
            DoctorSchedule.objects.create(doctor=self.doctor, weekday=weekday, start_time=time(9), end_time=time(11))

        self.patient = self.make_patient("pat@bsu.test", "Joshua", "Ejiofor")
        self.other = self.make_patient("other@bsu.test", "Ada", "Okafor")
        self.day = future_weekday()

    def make_patient(self, email, first, last):
        user = User.objects.create_user(email, email, "Pass@12345", first_name=first, last_name=last)
        PatientProfile.objects.create(user=user, phone="08012345678")
        return user

    def book(self, patient=None, day=None, start=time(9), reason="Persistent headache for two days."):
        return services.book_appointment(
            patient=patient or self.patient, doctor=self.doctor, day=day or self.day, start=start, reason=reason
        )


class SlotTests(PortalTestCase):
    def test_slot_generation_respects_windows_and_length(self):
        starts = generate_slot_starts([(time(9), time(10)), (time(14), time(15))], 30)
        self.assertEqual(starts, [time(9), time(9, 30), time(14), time(14, 30)])

    def test_booked_slot_disappears_from_availability(self):
        self.assertIn(time(9), get_available_slots(self.doctor, self.day))
        self.book(start=time(9))
        self.assertNotIn(time(9), get_available_slots(self.doctor, self.day))

    def test_same_slot_cannot_be_booked_twice(self):
        self.book(start=time(9))
        with self.assertRaises(SlotUnavailable):
            self.book(patient=self.other, start=time(9))

    def test_patient_cannot_book_same_doctor_twice_in_one_day(self):
        self.book(start=time(9))
        with self.assertRaises(BookingError):
            self.book(start=time(10))

    def test_past_dates_and_far_future_dates_are_rejected(self):
        with self.assertRaises(BookingError):
            self.book(day=timezone.localdate() - timedelta(days=1))
        with self.assertRaises(BookingError):
            self.book(day=timezone.localdate() + timedelta(days=400))


class AppointmentCodeTests(PortalTestCase):
    def test_codes_have_expected_shape(self):
        appt = self.book()
        self.assertTrue(appt.reference.startswith("BSU"))
        self.assertEqual(len(appt.reference), 9)
        self.assertEqual(len(appt.token), 16)
        self.assertTrue(appt.display_id.startswith("BSU-"))
        self.assertEqual(appt.display_token.count("-"), 3)

    def test_masked_names_hide_most_letters(self):
        masked = mask_name("Joshua Ejiofor")
        self.assertNotIn("Joshua", masked)
        self.assertNotIn("Ejiofor", masked)
        self.assertTrue(masked.startswith("J"))


class VerificationTests(PortalTestCase):
    def test_verify_by_id_and_by_token(self):
        appt = self.book()
        for code in (appt.display_id, appt.display_token, appt.display_token.lower().replace("-", " ")):
            response = self.client.get(reverse("verify"), {"code": code})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context["verdict"]["title"], "Valid appointment", code)

    def test_unknown_code_is_reported(self):
        response = self.client.get(reverse("verify"), {"code": "BSU-ZZZZZZ"})
        self.assertEqual(response.context["verdict"]["title"], "No matching appointment")

    def test_verification_page_hides_full_patient_name(self):
        appt = self.book()
        response = self.client.get(reverse("verify"), {"code": appt.display_id})
        self.assertNotContains(response, "Joshua Ejiofor")
        self.assertContains(response, appt.masked_patient_name)

    def test_cancelled_letter_stops_verifying(self):
        appt = self.book()
        services.cancel_appointment(appt, reason="Feeling better")
        response = self.client.get(reverse("verify"), {"code": appt.token})
        self.assertEqual(response.context["verdict"]["title"], "Cancelled")


class LetterAndAccessTests(PortalTestCase):
    def test_patient_downloads_pdf_letter(self):
        appt = self.book()
        self.client.force_login(self.patient)
        response = self.client.get(reverse("appointment_letter", args=[appt.reference]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_other_patients_cannot_see_or_download_an_appointment(self):
        appt = self.book()
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse("appointment_detail", args=[appt.reference])).status_code, 404)
        self.assertEqual(self.client.get(reverse("appointment_letter", args=[appt.reference])).status_code, 404)

    def test_cancelled_appointment_has_no_letter(self):
        appt = self.book()
        services.cancel_appointment(appt)
        self.client.force_login(self.patient)
        response = self.client.get(reverse("appointment_letter", args=[appt.reference]))
        self.assertEqual(response.status_code, 302)

    def test_doctor_portal_is_forbidden_to_patients(self):
        self.client.force_login(self.patient)
        self.assertEqual(self.client.get(reverse("doctor_dashboard")).status_code, 403)

    def test_doctor_records_completed_visit_and_notes(self):
        appt = Appointment.objects.create(
            patient=self.patient, patient_name="Joshua Ejiofor", doctor=self.doctor,
            date=timezone.localdate() - timedelta(days=1), start_time=time(9), end_time=time(9, 30),
            reason="Follow-up on blood pressure.",
        )
        self.client.force_login(self.doc_user)
        self.assertEqual(self.client.get(reverse("doctor_dashboard")).status_code, 200)
        self.client.post(reverse("doctor_appointment_status", args=[appt.reference]), {"action": "complete"})
        appt.refresh_from_db()
        self.assertEqual(appt.status, Appointment.Status.COMPLETED)

        self.client.post(reverse("doctor_appointment", args=[appt.reference]), {"doctor_notes": "BP stable."})
        appt.refresh_from_db()
        self.assertEqual(appt.doctor_notes, "BP stable.")

    def test_doctors_cannot_record_outcome_for_future_visits(self):
        appt = self.book()
        with self.assertRaises(BookingError):
            services.record_outcome(appt, Appointment.Status.COMPLETED)


class ChangeRuleTests(PortalTestCase):
    def test_cancellation_blocked_inside_the_cutoff_window(self):
        appt = self.book()
        with override_settings(CHANGE_CUTOFF_HOURS=10 ** 6):
            with self.assertRaises(BookingError):
                services.cancel_appointment(appt)
        appt.refresh_from_db()
        self.assertEqual(appt.status, Appointment.Status.SCHEDULED)

    def test_reschedule_moves_visit_and_frees_old_slot(self):
        appt = self.book(start=time(9))
        services.reschedule_appointment(appt, day=self.day, start=time(10))
        appt.refresh_from_db()
        self.assertEqual(appt.start_time, time(10))
        self.assertIn(time(9), get_available_slots(self.doctor, self.day))


class BookingViewTests(PortalTestCase):
    def test_booking_form_creates_appointment_and_redirects(self):
        self.client.force_login(self.patient)
        response = self.client.post(reverse("book"), {
            "doctor": self.doctor.pk, "date": self.day.isoformat(), "start_time": "09:30",
            "reason": "Cough and sore throat since Monday.",
        })
        appt = Appointment.objects.get(patient=self.patient)
        self.assertRedirects(response, appt.get_absolute_url())
        self.assertEqual(appt.start_time, time(9, 30))

    def test_slots_api_returns_free_times(self):
        self.client.force_login(self.patient)
        response = self.client.get(reverse("api_slots"), {"doctor": self.doctor.pk, "date": self.day.isoformat()})
        self.assertEqual(response.status_code, 200)
        values = [slot["value"] for slot in response.json()["slots"]]
        self.assertEqual(values, ["09:00", "09:30", "10:00", "10:30"])

    def test_slots_api_rejects_bad_input(self):
        self.client.force_login(self.patient)
        self.assertEqual(self.client.get(reverse("api_slots"), {"doctor": "x", "date": "2026-01-01"}).status_code, 400)


class AccountTests(TestCase):
    def test_signup_creates_patient_and_login_works_with_email_in_any_case(self):
        response = self.client.post(reverse("signup"), {
            "first_name": "Grace", "last_name": "Ortom", "email": "Grace.Ortom@Example.com",
            "phone": "08099990000", "password1": "Sturdy#Passphrase9", "password2": "Sturdy#Passphrase9",
            "terms": "on",
        })
        self.assertRedirects(response, reverse("dashboard"))
        user = User.objects.get(username="grace.ortom@example.com")
        self.assertEqual(user.patient_profile.phone, "08099990000")

        self.client.logout()
        response = self.client.post(reverse("login"), {
            "username": "GRACE.ORTOM@example.com", "password": "Sturdy#Passphrase9", "remember_me": "",
        })
        self.assertRedirects(response, reverse("dashboard"), fetch_redirect_response=False)

    def test_signup_rejects_duplicate_email_and_mismatched_passwords(self):
        User.objects.create_user("dup@bsu.test", "dup@bsu.test", "Pass@12345")
        response = self.client.post(reverse("signup"), {
            "first_name": "A", "last_name": "B", "email": "dup@bsu.test", "phone": "08012345678",
            "password1": "Sturdy#Passphrase9", "password2": "different", "terms": "on",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already exists")
        self.assertContains(response, "do not match")

    def test_weak_password_is_rejected(self):
        response = self.client.post(reverse("signup"), {
            "first_name": "A", "last_name": "B", "email": "weak@bsu.test", "phone": "08012345678",
            "password1": "12345678", "password2": "12345678", "terms": "on",
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="weak@bsu.test").exists())


class ReminderAndSeedTests(PortalTestCase):
    def test_reminders_are_sent_once(self):
        Appointment.objects.create(
            patient=self.patient, patient_name="Joshua Ejiofor", doctor=self.doctor,
            date=timezone.localdate() + timedelta(days=1), start_time=time(9), end_time=time(9, 30), reason="Check-up.",
        )
        self.assertEqual(services.send_due_reminders(), 1)
        self.assertEqual(services.send_due_reminders(), 0)

    def test_departments_are_seeded(self):
        self.assertGreaterEqual(Department.objects.count(), 10)

    def test_seed_demo_command_runs_and_is_repeatable(self):
        call_command("seed_demo", verbosity=0)
        call_command("seed_demo", verbosity=0)
        self.assertTrue(User.objects.filter(username="patient@bsu.demo").exists())
        self.assertEqual(Doctor.objects.filter(user__email__endswith="@bsu.demo").count(), 6)
