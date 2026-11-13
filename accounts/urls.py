from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views

urlpatterns = [
    path("signup/", views.signup, name="signup"),
    path("login/", views.PortalLoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("profile/", views.profile, name="profile"),
    path("password/change/", views.PortalPasswordChangeView.as_view(), name="password_change"),
    path(
        "password/reset/",
        auth_views.PasswordResetView.as_view(
            template_name="accounts/auth_card.html",
            email_template_name="registration/password_reset_email.html",
            subject_template_name="registration/password_reset_subject.txt",
            success_url=reverse_lazy("password_reset_done"),
            extra_context={
                "title": "Reset your password",
                "intro": "Enter the email address on your account and we will send you a secure reset link.",
                "submit_label": "Send reset link",
                "alt_link_url": reverse_lazy("login"),
                "alt_link_text": "Back to sign in",
            },
        ),
        name="password_reset",
    ),
    path(
        "password/reset/sent/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="accounts/message.html",
            extra_context={
                "title": "Check your inbox",
                "body": "If an account exists for that address, a reset link is on its way. The link expires in two hours.",
                "action_url": reverse_lazy("login"),
                "action_label": "Back to sign in",
            },
        ),
        name="password_reset_done",
    ),
    path(
        "password/reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="accounts/auth_card.html",
            success_url=reverse_lazy("password_reset_complete"),
            extra_context={
                "title": "Choose a new password",
                "intro": "Your new password must be at least 8 characters and not easy to guess.",
                "submit_label": "Save new password",
            },
        ),
        name="password_reset_confirm",
    ),
    path(
        "password/reset/complete/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="accounts/message.html",
            extra_context={
                "title": "Password updated",
                "body": "You can now sign in with your new password.",
                "action_url": reverse_lazy("login"),
                "action_label": "Sign in",
            },
        ),
        name="password_reset_complete",
    ),
]
