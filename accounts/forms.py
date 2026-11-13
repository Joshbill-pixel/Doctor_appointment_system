from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .models import PatientProfile
from .validators import validate_phone


class SignupForm(forms.Form):
    first_name = forms.CharField(label="First name", max_length=60)
    last_name = forms.CharField(label="Last name", max_length=60)
    email = forms.EmailField(label="Email address", max_length=150, widget=forms.EmailInput(attrs={"autocomplete": "email"}))
    phone = forms.CharField(label="Phone number", max_length=20, validators=[validate_phone],
                            widget=forms.TextInput(attrs={"autocomplete": "tel", "placeholder": "08012345678"}))
    password1 = forms.CharField(label="Password", strip=False,
                                widget=forms.PasswordInput(attrs={"autocomplete": "new-password", "data-password-meter": ""}))
    password2 = forms.CharField(label="Confirm password", strip=False,
                                widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))
    terms = forms.BooleanField(
        label="I agree to the patient terms and understand that appointment details are kept confidential.",
        error_messages={"required": "Please accept the terms to create your account."},
    )

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(username=email).exists() or User.objects.filter(email__iexact=email).exists():
            raise ValidationError("An account with this email already exists. Try signing in instead.")
        return email

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "The two passwords do not match.")
        if p1 and cleaned.get("email"):
            candidate = User(username=cleaned["email"], email=cleaned["email"],
                             first_name=cleaned.get("first_name", ""), last_name=cleaned.get("last_name", ""))
            try:
                validate_password(p1, user=candidate)
            except ValidationError as exc:
                self.add_error("password1", exc)
        return cleaned

    def save(self):
        data = self.cleaned_data
        user = User.objects.create_user(
            username=data["email"], email=data["email"], password=data["password1"],
            first_name=data["first_name"].strip(), last_name=data["last_name"].strip(),
        )
        PatientProfile.objects.create(user=user, phone=data["phone"].strip())
        return user


class EmailLoginForm(AuthenticationForm):
    username = forms.EmailField(label="Email address", widget=forms.EmailInput(attrs={"autocomplete": "email", "autofocus": True}))
    remember_me = forms.BooleanField(label="Keep me signed in", required=False, initial=True)

    def clean_username(self):
        return self.cleaned_data["username"].strip().lower()


class ProfileForm(forms.Form):
    first_name = forms.CharField(label="First name", max_length=60)
    last_name = forms.CharField(label="Last name", max_length=60)
    phone = forms.CharField(label="Phone number", max_length=20, validators=[validate_phone])
    date_of_birth = forms.DateField(label="Date of birth", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    gender = forms.ChoiceField(label="Gender", required=False, choices=[("", "Select…")] + list(PatientProfile.Gender.choices))
    address = forms.CharField(label="Home address", required=False, widget=forms.Textarea(attrs={"rows": 3}))
