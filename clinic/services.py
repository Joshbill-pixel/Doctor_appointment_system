"""Business rules for availability, booking, rescheduling, cancelling and notifications.

Views stay thin: anything that changes appointments goes through this module
so the rules are enforced the same way everywhere (portal, API, admin, tests).
"""
from datetime import date as date_cls, datetime, time, timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone

from .models import Appointment, Doctor, Notification


class BookingError(Exception):
    """A rule was broken (past date, outside booking window, duplicate booking, ...)."""


class SlotUnavailable(BookingError):
    """The chosen time is no longer free."""


def full_name(user):
    return user.get_full_name() or user.username


def generate_slot_starts(windows, slot_minutes):
    """Pure helper: turns (start, end) time windows into consecutive slot start times."""
    anchor = date_cls(2000, 1, 1)
    step = timedelta(minutes=slot_minutes)
    starts = set()
    for start, end in windows:
        cursor = datetime.combine(anchor, start)
        limit = datetime.combine(anchor, end)
        while cursor + step <= limit:
            starts.add(cursor.time())
            cursor += step
    return sorted(starts)


def get_available_slots(doctor, day, exclude_appointment_id=None):
    """Free start times for a doctor on a given day, honouring schedule, bookings and the clock."""
    if not doctor.is_accepting or not doctor.user.is_active:
        return []
    windows = doctor.schedules.filter(weekday=day.weekday()).values_list("start_time", "end_time")
    starts = generate_slot_starts(list(windows), doctor.slot_minutes)

    booked = set(
        Appointment.objects.filter(doctor=doctor, date=day, status=Appointment.Status.SCHEDULED)
        .exclude(pk=exclude_appointment_id)
        .values_list("start_time", flat=True)
    )
    now = timezone.localtime()
    free = []
    for start in starts:
        if start in booked:
            continue
        if day == now.date() and start <= now.time():
            continue
        free.append(start)
    return free


def check_booking_day(day):
    today = timezone.localdate()
    if day < today:
        raise BookingError("Please choose today or a date in the future.")
    if day > today + timedelta(days=settings.BOOKING_WINDOW_DAYS):
        raise BookingError(f"Appointments can be booked up to {settings.BOOKING_WINDOW_DAYS} days ahead.")


def _end_time(start, minutes):
    return (datetime.combine(date_cls(2000, 1, 1), start) + timedelta(minutes=minutes)).time()


def _send_email(user, subject, message):
    if user.email:
        send_mail(
            f"{subject} · {settings.CLINIC_NAME}",
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=True,
        )


def notify(user, title, message, link="", email=True):
    Notification.objects.create(user=user, title=title, message=message, link=link)
    if email:
        _send_email(user, title, f"Hello {full_name(user)},\n\n{message}\n\n{settings.CLINIC_NAME}")


def _visit_summary(appt):
    time_label = appt.start_time.strftime("%I:%M %p").lstrip("0")
    return (
        f"{appt.doctor.display_name} ({appt.department.title}) on "
        f"{appt.date.strftime('%A, %d %B %Y')} at {time_label}"
    )


@transaction.atomic
def book_appointment(*, patient, doctor, day, start, reason):
    check_booking_day(day)
    if not doctor.is_accepting:
        raise BookingError("This doctor is not accepting new bookings right now.")
    if start not in get_available_slots(doctor, day):
        raise SlotUnavailable("That time has just been taken or is no longer available. Please choose another slot.")
    if Appointment.objects.filter(patient=patient, doctor=doctor, date=day,
                                  status=Appointment.Status.SCHEDULED).exists():
        raise BookingError("You already have an appointment with this doctor that day.")

    try:
        with transaction.atomic():
            appt = Appointment.objects.create(
                patient=patient,
                patient_name=full_name(patient),
                doctor=doctor,
                date=day,
                start_time=start,
                end_time=_end_time(start, doctor.slot_minutes),
                reason=reason,
            )
    except IntegrityError:
        raise SlotUnavailable("That slot was just booked by someone else. Please choose another time.")

    notify(
        patient,
        "Appointment confirmed",
        f"Your appointment {appt.display_id} is confirmed: {_visit_summary(appt)}. "
        f"Download your letter from the portal and bring it on the day.",
        link=appt.get_absolute_url(),
    )
    notify(
        doctor.user,
        "New appointment booked",
        f"{appt.patient_name} booked {appt.display_id}: {_visit_summary(appt)}.",
        link=reverse("doctor_appointment", args=[appt.reference]),
    )
    return appt


@transaction.atomic
def reschedule_appointment(appt, *, day, start):
    if not appt.can_change:
        raise BookingError("This appointment can no longer be changed. Please contact the clinic.")
    check_booking_day(day)
    if start not in get_available_slots(appt.doctor, day, exclude_appointment_id=appt.pk):
        raise SlotUnavailable("That slot is not available. Please choose another time.")

    old_summary = _visit_summary(appt)
    appt.date = day
    appt.start_time = start
    appt.end_time = _end_time(start, appt.doctor.slot_minutes)
    appt.reminder_sent_at = None  # the new date gets its own reminder
    try:
        with transaction.atomic():
            appt.save(update_fields=["date", "start_time", "end_time", "reminder_sent_at", "updated_at"])
    except IntegrityError:
        raise SlotUnavailable("That slot was just booked by someone else. Please choose another time.")

    notify(
        appt.patient,
        "Appointment rescheduled",
        f"Appointment {appt.display_id} moved from {old_summary} to {_visit_summary(appt)}. "
        f"Your letter has been updated; please print the new one.",
        link=appt.get_absolute_url(),
    )
    notify(
        appt.doctor.user,
        "Appointment rescheduled",
        f"{appt.patient_name} moved {appt.display_id} to {_visit_summary(appt)}.",
        link=reverse("doctor_appointment", args=[appt.reference]),
    )
    return appt


def cancel_appointment(appt, *, reason="", by_doctor=False):
    if appt.status != Appointment.Status.SCHEDULED:
        raise BookingError("Only scheduled appointments can be cancelled.")
    if not by_doctor and not appt.can_change:
        raise BookingError(
            f"Cancellations close {settings.CHANGE_CUTOFF_HOURS} hours before the visit. "
            "Please call the clinic for help."
        )
    appt.status = Appointment.Status.CANCELLED
    appt.cancel_reason = (reason or "")[:255]
    appt.cancelled_at = timezone.now()
    appt.save(update_fields=["status", "cancel_reason", "cancelled_at", "updated_at"])

    who = "The clinic" if by_doctor else appt.patient_name
    notify(
        appt.patient,
        "Appointment cancelled",
        f"Appointment {appt.display_id} ({_visit_summary(appt)}) has been cancelled. "
        f"Its letter is no longer valid.",
        link=appt.get_absolute_url(),
    )
    if not by_doctor:
        notify(
            appt.doctor.user,
            "Appointment cancelled by patient",
            f"{who} cancelled {appt.display_id} ({_visit_summary(appt)}).",
            link=reverse("doctor_appointment", args=[appt.reference]),
        )
    return appt


def record_outcome(appt, outcome):
    """Doctor marks a scheduled visit as completed or as a no-show."""
    if appt.status != Appointment.Status.SCHEDULED:
        raise BookingError("This appointment already has an outcome.")
    if appt.date > timezone.localdate():
        raise BookingError("You can only record the outcome of a visit on or after its date.")
    if outcome not in (Appointment.Status.COMPLETED, Appointment.Status.NO_SHOW):
        raise BookingError("Unsupported outcome.")
    appt.status = outcome
    appt.save(update_fields=["status", "updated_at"])
    if outcome == Appointment.Status.COMPLETED:
        notify(
            appt.patient,
            "How was your visit?",
            f"Thank you for visiting {appt.doctor.display_name}. Please rate your experience in the portal.",
            link=reverse("appointment_feedback", args=[appt.reference]),
            email=False,
        )
    else:
        notify(
            appt.patient,
            "Missed appointment",
            f"We did not record a visit for {appt.display_id}. You can book a new appointment at any time.",
            link=reverse("book"),
        )
    return appt


def send_due_reminders(now=None):
    """Emails and notifies patients whose visit is tomorrow. Safe to run repeatedly."""
    now = now or timezone.now()
    tomorrow = timezone.localtime(now).date() + timedelta(days=1)
    due = Appointment.objects.select_related("patient", "doctor__user", "doctor__department").filter(
        date=tomorrow, status=Appointment.Status.SCHEDULED, reminder_sent_at__isnull=True
    )
    sent = 0
    for appt in due:
        notify(
            appt.patient,
            "Reminder: your visit is tomorrow",
            f"Reminder: {_visit_summary(appt)}. Bring your appointment letter ({appt.display_id}).",
            link=appt.get_absolute_url(),
        )
        appt.reminder_sent_at = now
        appt.save(update_fields=["reminder_sent_at"])
        sent += 1
    return sent
