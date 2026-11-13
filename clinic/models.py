import re
import secrets
from datetime import datetime, timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

# Characters that cannot be confused when read aloud or printed (no 0/O, 1/I/L).
CODE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
REFERENCE_PREFIX = "BSU"


def random_code(length):
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(length))


def normalize_code(value):
    """Turns 'bsu-k7q2 x9' or 'k7q2-x9…' into a comparable upper-case string."""
    return re.sub(r"[^A-Za-z0-9]", "", value or "").upper()


def mask_name(name):
    """'Joshua Ejiofor' -> 'J****** E******' (public verification never shows full names)."""
    parts = [p for p in (name or "").split() if p]
    if not parts:
        return "—"
    return " ".join(p[0] + "*" * min(max(len(p) - 1, 3), 8) for p in parts)


class Department(models.Model):
    title = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=8, default="🩺", help_text="An emoji shown on the department card.")
    is_active = models.BooleanField(default=True)
    created_on = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["title"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)[:200]
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class Doctor(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="doctor_profile")
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="doctors")
    title = models.CharField(max_length=20, default="Dr.")
    specialty = models.CharField(max_length=150, blank=True)
    bio = models.TextField(blank=True)
    slot_minutes = models.PositiveSmallIntegerField(
        default=20,
        validators=[MinValueValidator(10), MaxValueValidator(60)],
        help_text="Length of one consultation slot in minutes.",
    )
    is_accepting = models.BooleanField(default=True, help_text="Untick to pause new bookings for this doctor.")
    created_on = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["user__last_name", "user__first_name"]

    @property
    def full_name(self):
        return self.user.get_full_name() or self.user.username

    @property
    def display_name(self):
        return f"{self.title} {self.full_name}".strip()

    @property
    def initials(self):
        letters = [p[0] for p in self.full_name.split()[:2] if p]
        return "".join(letters).upper() or "DR"

    def __str__(self):
        return self.display_name


class DoctorSchedule(models.Model):
    class Weekday(models.IntegerChoices):
        MONDAY = 0, "Monday"
        TUESDAY = 1, "Tuesday"
        WEDNESDAY = 2, "Wednesday"
        THURSDAY = 3, "Thursday"
        FRIDAY = 4, "Friday"
        SATURDAY = 5, "Saturday"
        SUNDAY = 6, "Sunday"

    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name="schedules")
    weekday = models.PositiveSmallIntegerField(choices=Weekday.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        ordering = ["weekday", "start_time"]
        constraints = [
            models.CheckConstraint(condition=Q(end_time__gt=F("start_time")), name="schedule_end_after_start"),
        ]

    def clean(self):
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValidationError("The end time must be after the start time.")

    def __str__(self):
        return f"{self.doctor} · {self.get_weekday_display()} {self.start_time:%H:%M}–{self.end_time:%H:%M}"


class Appointment(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"
        NO_SHOW = "no_show", "Missed (no-show)"

    reference = models.CharField(max_length=16, unique=True, editable=False,
                                 help_text="Public appointment ID printed on the letter.")
    token = models.CharField(max_length=20, unique=True, editable=False,
                             help_text="Secret verification token printed and encoded in the QR code.")
    patient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="appointments")
    patient_name = models.CharField(max_length=150)
    doctor = models.ForeignKey(Doctor, on_delete=models.PROTECT, related_name="appointments")
    date = models.DateField(db_index=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    reason = models.TextField(max_length=1000)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.SCHEDULED, db_index=True)

    # Private to the clinical team; never shown to the patient or on the letter.
    doctor_notes = models.TextField(blank=True)

    cancel_reason = models.CharField(max_length=255, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    reminder_sent_at = models.DateTimeField(null=True, blank=True)
    rating = models.PositiveSmallIntegerField(null=True, blank=True,
                                              validators=[MinValueValidator(1), MaxValueValidator(5)])
    feedback = models.TextField(blank=True, max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["date", "start_time"]
        constraints = [
            # Two patients can never hold the same live slot with the same doctor.
            models.UniqueConstraint(
                fields=["doctor", "date", "start_time"],
                condition=Q(status="scheduled"),
                name="unique_active_doctor_slot",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = self._unique_value("reference", REFERENCE_PREFIX, 6)
        if not self.token:
            self.token = self._unique_value("token", "", 16)
        super().save(*args, **kwargs)

    def _unique_value(self, field, prefix, length):
        while True:
            value = prefix + random_code(length)
            if not Appointment.objects.filter(**{field: value}).exists():
                return value

    def __str__(self):
        return f"{self.display_id} · {self.patient_name} · {self.date}"

    def get_absolute_url(self):
        return reverse("appointment_detail", args=[self.reference])

    @property
    def display_id(self):
        return f"{REFERENCE_PREFIX}-{self.reference[len(REFERENCE_PREFIX):]}"

    @property
    def display_token(self):
        return "-".join(self.token[i:i + 4] for i in range(0, len(self.token), 4))

    @property
    def department(self):
        return self.doctor.department

    @property
    def starts_at(self):
        naive = datetime.combine(self.date, self.start_time)
        return timezone.make_aware(naive, timezone.get_current_timezone())

    @property
    def is_upcoming(self):
        return self.status == self.Status.SCHEDULED and self.starts_at >= timezone.now()

    @property
    def can_change(self):
        """Patients may cancel or reschedule until the cutoff before the visit."""
        if self.status != self.Status.SCHEDULED:
            return False
        cutoff = timezone.now() + timedelta(hours=settings.CHANGE_CUTOFF_HOURS)
        return self.starts_at >= cutoff

    @property
    def masked_patient_name(self):
        return mask_name(self.patient_name)

    @property
    def status_tone(self):
        return {
            self.Status.SCHEDULED: "info",
            self.Status.COMPLETED: "success",
            self.Status.CANCELLED: "danger",
            self.Status.NO_SHOW: "warning",
        }[self.status]


class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField(max_length=150)
    message = models.TextField()
    link = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} → {self.user}"
