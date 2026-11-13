from datetime import date as date_cls, timedelta
from functools import wraps
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from . import services
from .forms import BookingForm, CancelForm, DoctorNotesForm, FeedbackForm, RescheduleForm
from .letter import build_appointment_letter
from .models import Appointment, Department, Doctor, Notification, normalize_code

Status = Appointment.Status


# ---------------------------------------------------------------- helpers

def _patient_appointment(request, ref):
    return get_object_or_404(
        Appointment.objects.select_related("doctor__user", "doctor__department"),
        reference=normalize_code(ref),
        patient=request.user,
    )


def doctor_required(view_func):
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        doctor = getattr(request.user, "doctor_profile", None)
        if doctor is None:
            raise PermissionDenied
        return view_func(request, doctor, *args, **kwargs)

    return wrapper


def _verdict(appt):
    today = timezone.localdate()
    if appt is None:
        return {"tone": "danger", "title": "No matching appointment",
                "message": "We could not find an appointment with that ID or token. Check the characters on the "
                           "letter and try again."}
    if appt.status == Status.CANCELLED:
        return {"tone": "danger", "title": "Cancelled",
                "message": "This appointment was cancelled. The letter is no longer valid."}
    if appt.status == Status.COMPLETED:
        return {"tone": "success", "title": "Visit completed",
                "message": "This appointment was attended and recorded as completed."}
    if appt.status == Status.NO_SHOW:
        return {"tone": "warning", "title": "Not attended",
                "message": "The patient did not attend this appointment."}
    if appt.date < today:
        return {"tone": "warning", "title": "Visit date has passed",
                "message": "This appointment is still marked as scheduled but its date has passed."}
    return {"tone": "success", "title": "Valid appointment",
            "message": "This letter is genuine and the appointment is scheduled."}


# ---------------------------------------------------------------- public pages

def home(request):
    departments = Department.objects.filter(is_active=True).annotate(
        doctor_count=Count("doctors", distinct=True)
    )
    doctors = Doctor.objects.filter(is_accepting=True, user__is_active=True).select_related("user", "department")[:4]
    stats = {
        "doctors": Doctor.objects.filter(user__is_active=True).count(),
        "departments": departments.count(),
        "completed": Appointment.objects.filter(status=Status.COMPLETED).count(),
    }
    return render(request, "clinic/home.html", {"departments": departments, "doctors": doctors, "stats": stats})


def doctors(request):
    qs = Doctor.objects.filter(user__is_active=True).select_related("user", "department")
    dept = request.GET.get("dept", "").strip()
    q = request.GET.get("q", "").strip()
    if dept:
        qs = qs.filter(department__slug=dept)
    if q:
        qs = qs.filter(
            Q(user__first_name__icontains=q) | Q(user__last_name__icontains=q)
            | Q(specialty__icontains=q) | Q(department__title__icontains=q)
        )
    return render(request, "clinic/doctors.html", {
        "doctors": qs,
        "departments": Department.objects.filter(is_active=True),
        "active_dept": dept,
        "q": q,
    })


# ---------------------------------------------------------------- booking

@login_required
def book(request):
    initial = {}
    if request.method == "GET":
        initial = {"doctor": request.GET.get("doctor", ""), "date": request.GET.get("date", "")}
    form = BookingForm(request.POST or None, initial=initial)

    if request.method == "POST" and form.is_valid():
        try:
            appt = services.book_appointment(
                patient=request.user,
                doctor=form.cleaned_data["doctor"],
                day=form.cleaned_data["date"],
                start=form.cleaned_data["start_time"],
                reason=form.cleaned_data["reason"],
            )
        except services.BookingError as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, f"Appointment {appt.display_id} is confirmed. Your letter is ready to print.")
            return redirect(appt.get_absolute_url())

    return render(request, "clinic/book.html", {
        "form": form,
        "doctors": Doctor.objects.filter(is_accepting=True, user__is_active=True).select_related("user", "department"),
        "departments": Department.objects.filter(is_active=True),
        "max_date": timezone.localdate() + timedelta(days=settings.BOOKING_WINDOW_DAYS),
    })


@login_required
@require_GET
def api_slots(request):
    """JSON feed used by the slot picker: free times for one doctor on one day."""
    doctor_id = request.GET.get("doctor", "")
    if not doctor_id.isdigit():
        return JsonResponse({"error": "Choose a doctor first."}, status=400)
    doctor = Doctor.objects.filter(pk=doctor_id, user__is_active=True).select_related("user").first()
    if doctor is None:
        return JsonResponse({"error": "That doctor is not available."}, status=404)
    try:
        day = date_cls.fromisoformat(request.GET.get("date", ""))
    except ValueError:
        return JsonResponse({"error": "Choose a valid date."}, status=400)

    try:
        services.check_booking_day(day)
    except services.BookingError as exc:
        return JsonResponse({"date": day.isoformat(), "slots": [], "message": str(exc)})

    exclude_pk = None
    exclude_ref = request.GET.get("exclude", "")
    if exclude_ref:
        exclude_pk = Appointment.objects.filter(
            reference=normalize_code(exclude_ref), patient=request.user
        ).values_list("pk", flat=True).first()

    slots = services.get_available_slots(doctor, day, exclude_appointment_id=exclude_pk)
    return JsonResponse({
        "date": day.isoformat(),
        "slots": [{"value": s.strftime("%H:%M"), "label": s.strftime("%I:%M %p").lstrip("0")} for s in slots],
        "message": "" if slots else "No free slots on this day. Please try another date.",
    })


# ---------------------------------------------------------------- patient area

@login_required
def dashboard(request):
    if getattr(request.user, "doctor_profile", None) is not None:
        return redirect("doctor_dashboard")

    today = timezone.localdate()
    base = Appointment.objects.filter(patient=request.user).select_related("doctor__user", "doctor__department")
    upcoming = base.filter(status=Status.SCHEDULED, date__gte=today).order_by("date", "start_time")
    return render(request, "clinic/dashboard.html", {
        "next_appointment": upcoming.first(),
        "upcoming": list(upcoming[1:6]),
        "stats": {
            "upcoming": upcoming.count(),
            "completed": base.filter(status=Status.COMPLETED).count(),
            "total": base.count(),
        },
        "notifications": Notification.objects.filter(user=request.user)[:5],
    })


@login_required
def my_appointments(request):
    tab = request.GET.get("tab", "upcoming")
    today = timezone.localdate()
    qs = Appointment.objects.filter(patient=request.user).select_related("doctor__user", "doctor__department")
    if tab == "past":
        qs = qs.filter(Q(date__lt=today) | Q(status__in=[Status.COMPLETED, Status.CANCELLED, Status.NO_SHOW]))
        qs = qs.order_by("-date", "-start_time")
    elif tab == "upcoming":
        qs = qs.filter(status=Status.SCHEDULED, date__gte=today).order_by("date", "start_time")
    else:
        tab = "all"
        qs = qs.order_by("-date", "-start_time")
    return render(request, "clinic/appointments.html", {"appointments": qs, "tab": tab})


@login_required
def appointment_detail(request, ref):
    appt = _patient_appointment(request, ref)
    return render(request, "clinic/appointment_detail.html", {
        "appt": appt,
        "cancel_form": CancelForm(),
    })


@login_required
@require_POST
def appointment_cancel(request, ref):
    appt = _patient_appointment(request, ref)
    form = CancelForm(request.POST)
    reason = form.cleaned_data["reason"] if form.is_valid() else ""
    try:
        services.cancel_appointment(appt, reason=reason)
    except services.BookingError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f"Appointment {appt.display_id} has been cancelled.")
    return redirect(appt.get_absolute_url())


@login_required
def appointment_reschedule(request, ref):
    appt = _patient_appointment(request, ref)
    if not appt.can_change:
        messages.error(request, "This appointment can no longer be changed. Please contact the clinic.")
        return redirect(appt.get_absolute_url())

    form = RescheduleForm(request.POST or None, initial={
        "date": appt.date.isoformat(),
        "start_time": appt.start_time.strftime("%H:%M"),
    })
    if request.method == "POST" and form.is_valid():
        try:
            services.reschedule_appointment(
                appt, day=form.cleaned_data["date"], start=form.cleaned_data["start_time"]
            )
        except services.BookingError as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, f"Appointment {appt.display_id} has been rescheduled. Print your updated letter.")
            return redirect(appt.get_absolute_url())

    return render(request, "clinic/reschedule.html", {
        "appt": appt,
        "form": form,
        "max_date": timezone.localdate() + timedelta(days=settings.BOOKING_WINDOW_DAYS),
    })


@login_required
def appointment_feedback(request, ref):
    appt = _patient_appointment(request, ref)
    if appt.status != Status.COMPLETED:
        messages.error(request, "Feedback can be shared after a completed visit.")
        return redirect(appt.get_absolute_url())
    if appt.rating:
        messages.info(request, "You have already rated this visit. Thank you!")
        return redirect(appt.get_absolute_url())

    form = FeedbackForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        appt.rating = form.cleaned_data["rating"]
        appt.feedback = form.cleaned_data["feedback"].strip()
        appt.save(update_fields=["rating", "feedback", "updated_at"])
        messages.success(request, "Thank you for your feedback. It helps us improve care.")
        return redirect(appt.get_absolute_url())
    return render(request, "clinic/feedback.html", {"appt": appt, "form": form})


@login_required
def appointment_letter(request, ref):
    appt = _patient_appointment(request, ref)
    if appt.status == Status.CANCELLED:
        messages.error(request, "Cancelled appointments do not have a valid letter.")
        return redirect(appt.get_absolute_url())

    verify_url = f"{settings.SITE_URL}{reverse('verify')}?{urlencode({'code': appt.token})}"
    pdf = build_appointment_letter(appt, verify_url)
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{appt.display_id}-appointment-letter.pdf"'
    response["Cache-Control"] = "private, no-store"
    return response


# ---------------------------------------------------------------- verification (public)

def verify(request):
    raw = request.GET.get("code", "").strip()
    code = normalize_code(raw)
    appt = None
    if code:
        appt = (Appointment.objects.select_related("doctor__user", "doctor__department")
                .filter(Q(reference=code) | Q(token=code)).first())
    return render(request, "clinic/verify.html", {
        "raw_code": raw,
        "searched": bool(code),
        "appt": appt,
        "verdict": _verdict(appt) if code else None,
    })


# ---------------------------------------------------------------- notifications

@login_required
def notifications(request):
    items = Notification.objects.filter(user=request.user)[:100]
    return render(request, "clinic/notifications.html", {"items": items})


@login_required
@require_POST
def notifications_read_all(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    messages.success(request, "All notifications marked as read.")
    return redirect("notifications")


# ---------------------------------------------------------------- doctor portal

@doctor_required
def doctor_dashboard(request, doctor):
    today = timezone.localdate()
    try:
        day = date_cls.fromisoformat(request.GET.get("date", ""))
    except ValueError:
        day = today

    base = Appointment.objects.filter(doctor=doctor).select_related("patient", "patient__patient_profile")
    return render(request, "clinic/doctor_dashboard.html", {
        "doctor": doctor,
        "day": day,
        "is_today": day == today,
        "prev_day": day - timedelta(days=1),
        "next_day": day + timedelta(days=1),
        "day_appointments": base.filter(date=day).order_by("start_time"),
        "upcoming": base.filter(status=Status.SCHEDULED, date__gt=day, date__lte=today + timedelta(days=7))
                        .order_by("date", "start_time")[:10],
        "stats": {
            "today": base.filter(date=today).exclude(status=Status.CANCELLED).count(),
            "waiting": base.filter(date=day, status=Status.SCHEDULED).count(),
            "completed_week": base.filter(status=Status.COMPLETED, date__gte=today - timedelta(days=6)).count(),
            "no_shows_month": base.filter(status=Status.NO_SHOW, date__gte=today.replace(day=1)).count(),
        },
    })


@doctor_required
def doctor_appointment(request, doctor, ref):
    appt = get_object_or_404(
        Appointment.objects.select_related("patient__patient_profile", "doctor__user", "doctor__department"),
        reference=normalize_code(ref),
        doctor=doctor,
    )
    notes_form = DoctorNotesForm(request.POST or None, initial={"doctor_notes": appt.doctor_notes})
    if request.method == "POST" and notes_form.is_valid():
        appt.doctor_notes = notes_form.cleaned_data["doctor_notes"].strip()
        appt.save(update_fields=["doctor_notes", "updated_at"])
        messages.success(request, "Clinical notes saved.")
        return redirect("doctor_appointment", ref=appt.reference)

    return render(request, "clinic/doctor_appointment.html", {
        "appt": appt,
        "notes_form": notes_form,
        "profile": getattr(appt.patient, "patient_profile", None),
    })


@doctor_required
@require_POST
def doctor_appointment_status(request, doctor, ref):
    appt = get_object_or_404(Appointment, reference=normalize_code(ref), doctor=doctor)
    action = request.POST.get("action", "")
    try:
        if action == "complete":
            services.record_outcome(appt, Status.COMPLETED)
        elif action == "no_show":
            services.record_outcome(appt, Status.NO_SHOW)
        elif action == "cancel":
            services.cancel_appointment(
                appt, reason=request.POST.get("reason", "").strip() or "Cancelled by the clinic", by_doctor=True
            )
        else:
            raise services.BookingError("Unknown action.")
    except services.BookingError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Appointment updated.")
    return redirect("doctor_appointment", ref=appt.reference)
