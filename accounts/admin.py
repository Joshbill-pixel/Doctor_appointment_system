from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User

from .models import PatientProfile


class PatientProfileInline(admin.StackedInline):
    model = PatientProfile
    can_delete = False
    extra = 0


class PortalUserAdmin(UserAdmin):
    inlines = [PatientProfileInline]
    list_display = ("username", "first_name", "last_name", "email", "is_staff", "date_joined")
    search_fields = ("username", "email", "first_name", "last_name")


admin.site.unregister(User)
admin.site.register(User, PortalUserAdmin)
