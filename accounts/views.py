from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, PasswordChangeView
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy

from clinic.services import notify

from .forms import EmailLoginForm, ProfileForm, SignupForm
from .models import PatientProfile


def signup(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            user = form.save()
        login(request, user)
        notify(
            user,
            "Welcome to BSU Medical Centre",
            "Your account is ready. You can book a consultation at any time.",
            link=reverse("book"),
            email=False,
        )
        messages.success(request, "Welcome aboard! Your account has been created.")
        return redirect("dashboard")

    return render(request, "accounts/auth_card.html", {
        "title": "Create your patient account",
        "intro": "Book consultations, get a printable appointment letter and manage every visit in one place.",
        "form": form,
        "submit_label": "Create account",
        "alt_prompt": "Already registered?",
        "alt_link_url": reverse("login"),
        "alt_link_text": "Sign in",
        "wide": True,
    })


class PortalLoginView(LoginView):
    form_class = EmailLoginForm
    template_name = "accounts/auth_card.html"
    redirect_authenticated_user = True
    extra_context = {
        "title": "Welcome back",
        "intro": "Sign in with the email address you registered with.",
        "submit_label": "Sign in",
        "alt_prompt": "New to BSU Medical Centre?",
        "alt_link_url": reverse_lazy("signup"),
        "alt_link_text": "Create an account",
        "show_forgot": True,
    }

    def form_valid(self, form):
        response = super().form_valid(form)
        if not form.cleaned_data.get("remember_me"):
            self.request.session.set_expiry(0)  # browser-session only
        return response


class PortalPasswordChangeView(PasswordChangeView):
    template_name = "accounts/auth_card.html"
    success_url = reverse_lazy("profile")
    extra_context = {
        "title": "Change your password",
        "intro": "Choose a strong password you do not use anywhere else.",
        "submit_label": "Update password",
        "alt_link_url": reverse_lazy("profile"),
        "alt_link_text": "Back to profile",
    }

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Your password has been updated.")
        return response


@login_required
def profile(request):
    patient_profile, _ = PatientProfile.objects.get_or_create(user=request.user)
    user = request.user
    initial = {
        "first_name": user.first_name,
        "last_name": user.last_name,
        "phone": patient_profile.phone,
        "date_of_birth": patient_profile.date_of_birth,
        "gender": patient_profile.gender,
        "address": patient_profile.address,
    }
    form = ProfileForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        user.first_name = data["first_name"].strip()
        user.last_name = data["last_name"].strip()
        user.save(update_fields=["first_name", "last_name"])
        patient_profile.phone = data["phone"].strip()
        patient_profile.date_of_birth = data["date_of_birth"]
        patient_profile.gender = data["gender"]
        patient_profile.address = data["address"].strip()
        patient_profile.save()
        messages.success(request, "Your profile has been saved.")
        return redirect("profile")
    return render(request, "accounts/profile.html", {"form": form})
