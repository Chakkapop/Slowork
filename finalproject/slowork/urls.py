from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("jobs/", views.home, name="job_list"),
    path("register/", views.register, name="register"),
    path("profile/", views.profile_edit, name="profile"),
    path("jobs/create/", views.job_create, name="job_create"),
    path("jobs/<int:pk>/", views.job_detail, name="job_detail"),
    path("jobs/<int:pk>/edit/", views.job_update, name="job_update"),
    path("jobs/<int:pk>/delete/", views.job_delete, name="job_delete"),
    path("jobs/<int:pk>/applications/", views.job_applications, name="job_applications"),
    path("jobs/<int:pk>/complete/", views.job_mark_completed, name="job_mark_completed"),
    path(
        "jobs/<int:job_id>/apply/",
        views.application_create,
        name="application_create",
    ),
    path(
        "applications/<int:pk>/<str:action>/",
        views.application_update_status,
        name="application_update_status",
    ),
    path(
        "applications/<int:application_id>/submit/",
        views.work_submission_create,
        name="work_submission_create",
    ),
    path(
        "submissions/<int:submission_id>/<str:action>/",
        views.work_submission_update_status,
        name="work_submission_update_status",
    ),
    path(
        "jobs/<int:job_id>/review/<str:target>/",
        views.review_create,
        name="review_create",
    ),
    path("notifications/", views.notification_list, name="notifications"),
    path(
        "notifications/<int:pk>/read/",
        views.notification_mark_read,
        name="notification_mark_read",
    ),
]
