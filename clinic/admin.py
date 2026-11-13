from django.contrib import admin, messages

from . import services
from .models import Appointment, Department, Doctor, DoctorSchedule


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("icon", "title", "is_active", "created_on")
    list_display_links = ("title",)
    list_editable = ("is_active",)
    search_fields = ("title", "description")
    prepopulated_fields = {"slug": ("title",)}


class DoctorScheduleInline(admin.TabularInline):
    model = DoctorSchedule
    extra = 1


@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = ("display_name", "department", "specialty", "slot_minutes", "is_accepting")
    list_editable = ("is_accepting",)
    list_filter = ("department", "is_accepting")
    search_fields = ("user__first_name", "user__last_name", "user__email", "specialty")
    raw_id_fields = ("user",)
    inlines = [DoctorScheduleInline]
    fieldsets = (
        ("Account", {"fields": ("user", "department", "title", "specialty", "bio")}),
        ("Booking", {"fields": ("slot_minutes", "is_accepting")}),
    )


@admin.action(description="Mark selected as completed")
def mark_completed(modeladmin, request, queryset):
    _apply_outcome(modeladmin, request, queryset, Appointment.Status.COMPLETED)


@admin.action(description="Mark selected as no-show")
def mark_no_show(modeladmin, request, queryset):
    _apply_outcome(modeladmin, request, queryset, Appointment.Status.NO_SHOW)


def _apply_outcome(modeladmin, request, queryset, outcome):
    done, failed = 0, 0
    for appt in queryset:
        try:
            services.record_outcome(appt, outcome)
            done += 1
        except services.BookingError:
            failed += 1
    modeladmin.message_user(request, f"{done} updated, {failed} skipped.", messages.SUCCESS if done else messages.WARNING)


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("display_id", "patient_name", "doctor", "date", "start_time", "status", "rating")
    list_filter = ("status", "date", "doctor__department", "doctor")
    search_fields = ("reference", "token", "patient_name", "patient__email", "patient__username")
    readonly_fields = ("display_id", "display_token", "patient", "patient_name", "created_at", "updated_at",
                       "cancelled_at", "reminder_sent_at", "rating", "feedback")
    fields = ("display_id", "display_token", "status", "patient", "patient_name", "doctor", "date",
              "start_time", "end_time", "reason", "doctor_notes", "cancel_reason", "cancelled_at",
              "reminder_sent_at", "rating", "feedback", "created_at", "updated_at")
    date_hierarchy = "date"
    list_per_page = 50
    actions = [mark_completed, mark_no_show]
