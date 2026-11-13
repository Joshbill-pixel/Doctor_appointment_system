from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("doctors/", views.doctors, name="doctors"),
    path("book/", views.book, name="book"),
    path("api/slots/", views.api_slots, name="api_slots"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("appointments/", views.my_appointments, name="my_appointments"),
    path("appointments/<str:ref>/", views.appointment_detail, name="appointment_detail"),
    path("appointments/<str:ref>/letter.pdf", views.appointment_letter, name="appointment_letter"),
    path("appointments/<str:ref>/cancel/", views.appointment_cancel, name="appointment_cancel"),
    path("appointments/<str:ref>/reschedule/", views.appointment_reschedule, name="appointment_reschedule"),
    path("appointments/<str:ref>/feedback/", views.appointment_feedback, name="appointment_feedback"),
    path("verify/", views.verify, name="verify"),
    path("notifications/", views.notifications, name="notifications"),
    path("notifications/read-all/", views.notifications_read_all, name="notifications_read_all"),
    path("doctor/", views.doctor_dashboard, name="doctor_dashboard"),
    path("doctor/appointments/<str:ref>/", views.doctor_appointment, name="doctor_appointment"),
    path("doctor/appointments/<str:ref>/status/", views.doctor_appointment_status, name="doctor_appointment_status"),
]
