from datetime import datetime

from django import forms

from .models import Appointment, Doctor, normalize_code


class TimeSlotField(forms.Field):
    """Accepts 'HH:MM' from the slot picker and returns a time object."""

    widget = forms.HiddenInput
    default_error_messages = {
        "required": "Please choose an available time slot.",
        "invalid": "Please choose a valid time slot.",
    }

    def to_python(self, value):
        if value in self.empty_values:
            return None
        try:
            return datetime.strptime(str(value).strip(), "%H:%M").time()
        except ValueError:
            raise forms.ValidationError(self.error_messages["invalid"], code="invalid")


class BookingForm(forms.Form):
    doctor = forms.ModelChoiceField(
        queryset=Doctor.objects.none(),
        error_messages={"required": "Please choose a doctor.", "invalid_choice": "That doctor is not available."},
    )
    date = forms.DateField(
        label="Preferred date",
        widget=forms.DateInput(attrs={"type": "date"}),
        error_messages={"required": "Please choose a date.", "invalid": "Enter a valid date."},
    )
    start_time = TimeSlotField(label="Time slot", widget=forms.HiddenInput())
    reason = forms.CharField(
        label="What would you like help with?",
        min_length=10,
        max_length=1000,
        widget=forms.Textarea(attrs={"rows": 4, "placeholder": "Describe your symptoms or the reason for your visit…"}),
        error_messages={"min_length": "Please give a little more detail (at least 10 characters)."},
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["doctor"].queryset = Doctor.objects.filter(
            is_accepting=True, user__is_active=True
        ).select_related("user", "department")


class RescheduleForm(forms.Form):
    date = forms.DateField(
        label="New date",
        widget=forms.DateInput(attrs={"type": "date"}),
        error_messages={"required": "Please choose a date.", "invalid": "Enter a valid date."},
    )
    start_time = TimeSlotField(label="New time slot", widget=forms.HiddenInput())


class CancelForm(forms.Form):
    reason = forms.CharField(
        label="Reason (optional)", required=False, max_length=255,
        widget=forms.TextInput(attrs={"placeholder": "e.g. I am no longer unwell"}),
    )


class FeedbackForm(forms.Form):
    rating = forms.TypedChoiceField(
        label="How would you rate your visit?",
        choices=[(str(i), f"{i} star{'s' if i > 1 else ''}") for i in range(5, 0, -1)],
        coerce=int,
        widget=forms.RadioSelect,
        error_messages={"required": "Please choose a rating."},
    )
    feedback = forms.CharField(
        label="Anything you would like us to know? (optional)", required=False, max_length=1000,
        widget=forms.Textarea(attrs={"rows": 4}),
    )


class DoctorNotesForm(forms.Form):
    doctor_notes = forms.CharField(
        label="Private clinical notes",
        required=False,
        widget=forms.Textarea(attrs={"rows": 6, "placeholder": "Visible to clinical staff only."}),
    )
