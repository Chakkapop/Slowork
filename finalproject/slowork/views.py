from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import (
    ApplicationForm,
    JobFilterForm,
    JobForm,
    NotificationBulkUpdateForm,
    ProfileForm,
    ReviewForm,
    UserRegistrationForm,
    WorkSubmissionForm,
)
from .models import Application, Job, Notification, Review, User, WorkSubmission
from .services import create_notification


def home(request):
    jobs = (
        Job.objects.select_related("employer", "category")
        .annotate(application_total=Count("applications"))
        .order_by("-created_at")
    )
    filter_form = JobFilterForm(request.GET or None)
    if filter_form.is_valid():
        search = filter_form.cleaned_data["search"]
        if search:
            jobs = jobs.filter(
                Q(title__icontains=search)
                | Q(description__icontains=search)
                | Q(location_city__icontains=search)
            )
        category = filter_form.cleaned_data["category"]
        if category:
            jobs = jobs.filter(category=category)
        status = filter_form.cleaned_data["status"]
        if status:
            jobs = jobs.filter(status=status)
        posted = filter_form.cleaned_data["posted"]
        if posted:
            try:
                days = int(posted)
                cutoff = timezone.now() - timedelta(days=days)
                jobs = jobs.filter(created_at__gte=cutoff)
            except ValueError:
                pass
    else:
        filter_form = JobFilterForm()

    user_applied_job_ids: set[int] = set()
    if request.user.is_authenticated and request.user.is_freelancer:
        user_applied_job_ids = set(
            request.user.applications.values_list("job_id", flat=True)
        )

    context = {
        "jobs": jobs,
        "filter_form": filter_form,
        "user_applied_job_ids": user_applied_job_ids,
    }
    return render(request, "slowork/job_list.html", context)


def register(request):
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Welcome to Slowork! Your account is ready.")
            return redirect("home")
    else:
        form = UserRegistrationForm()
    return render(request, "slowork/register.html", {"form": form})


@login_required
def profile_edit(request):
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully.")
            return redirect("profile")
    else:
        form = ProfileForm(instance=request.user)
    return render(request, "slowork/profile_form.html", {"form": form})


def profile_view(request, user_id: int):
    """Public profile page showing ratings and reviews."""
    profile_user = get_object_or_404(
        User.objects.prefetch_related("reviews_received__reviewer", "reviews_received__job"),
        pk=user_id,
    )
    reviews = (
        profile_user.reviews_received.select_related("reviewer", "job")
        .order_by("-created_at")
    )

    pending_review_jobs: list[Job] = []
    review_target: str | None = None
    if request.user.is_authenticated and request.user != profile_user:
        if request.user.is_employer and profile_user.is_freelancer:
            pending_review_jobs = list(
                Job.objects.filter(
                    employer=request.user,
                    selected_application__freelancer=profile_user,
                    status=Job.STATUS_COMPLETED,
                )
                .exclude(
                    reviews__reviewer=request.user,
                    reviews__reviewee=profile_user,
                )
                .order_by("-updated_at")
                .distinct()
            )
            if pending_review_jobs:
                review_target = "freelancer"
        elif request.user.is_freelancer and profile_user.is_employer:
            pending_review_jobs = list(
                Job.objects.filter(
                    employer=profile_user,
                    selected_application__freelancer=request.user,
                    status=Job.STATUS_COMPLETED,
                )
                .exclude(
                    reviews__reviewer=request.user,
                    reviews__reviewee=profile_user,
                )
                .order_by("-updated_at")
                .distinct()
            )
            if pending_review_jobs:
                review_target = "employer"

    context = {
        "profile_user": profile_user,
        "reviews": reviews,
        "pending_review_jobs": pending_review_jobs,
        "review_target": review_target,
    }
    return render(request, "slowork/profile_detail.html", context)


@login_required
def job_create(request):
    if not request.user.is_employer:
        return HttpResponseForbidden("Only employers can post jobs.")

    if request.method == "POST":
        form = JobForm(request.POST)
        if form.is_valid():
            job = form.save(commit=False)
            job.employer = request.user
            job.status = Job.STATUS_OPEN
            job.save()
            messages.success(request, "Job posted successfully.")
            return redirect("job_detail", pk=job.pk)
    else:
        form = JobForm()
    return render(request, "slowork/job_form.html", {"form": form, "is_edit": False})


@login_required
def job_update(request, pk: int):
    job = get_object_or_404(Job, pk=pk)
    if job.employer != request.user and not request.user.is_market_admin:
        return HttpResponseForbidden("You do not have permission to edit this job.")

    if request.method == "POST":
        form = JobForm(request.POST, instance=job)
        if form.is_valid():
            form.save()
            messages.success(request, "Job updated successfully.")
            return redirect("job_detail", pk=job.pk)
    else:
        form = JobForm(instance=job)
    return render(request, "slowork/job_form.html", {"form": form, "is_edit": True, "job": job})


@login_required
def job_delete(request, pk: int):
    job = get_object_or_404(Job, pk=pk)
    if job.employer != request.user and not request.user.is_market_admin:
        return HttpResponseForbidden("You do not have permission to delete this job.")

    if request.method == "POST":
        job.delete()
        messages.success(request, "Job removed successfully.")
        return redirect("home")
    return render(request, "slowork/job_confirm_delete.html", {"job": job})


def job_detail(request, pk: int):
    job = get_object_or_404(
        Job.objects.select_related("employer", "category", "selected_application"),
        pk=pk,
    )
    applications = job.applications.select_related("freelancer").order_by("-created_at")
    submissions = job.submissions.select_related("submitted_by").order_by("-created_at")
    reviews = job.reviews.select_related("reviewer", "reviewee").order_by("-created_at")

    user_application = None
    application_form = None
    if request.user.is_authenticated and request.user.is_freelancer:
        user_application = applications.filter(freelancer=request.user).first()
        if not user_application and job.status == Job.STATUS_OPEN:
            application_form = ApplicationForm()

    context = {
        "job": job,
        "applications": applications,
        "submissions": submissions,
        "reviews": reviews,
        "user_application": user_application,
        "application_form": application_form,
    }
    return render(request, "slowork/job_detail.html", context)

@login_required
def employer_job_list(request):
    if not request.user.is_employer:
        return HttpResponseForbidden("Only employers can access this page.")
    jobs = Job.objects.filter(employer=request.user).order_by("-created_at")
    context = {"jobs": jobs}
    return render(request, "slowork/employer_job_list.html", context)

@login_required
def job_applications(request, pk: int):
    job = get_object_or_404(Job.objects.select_related("employer"), pk=pk)
    if job.employer != request.user and not request.user.is_market_admin:
        return HttpResponseForbidden("You do not have permission to view applications for this job.")
    applications = job.applications.select_related("freelancer").order_by("-created_at")
    return render(
        request,
        "slowork/application_list.html",
        {"job": job, "applications": applications},
    )


@login_required
def application_create(request, job_id: int):
    job = get_object_or_404(Job, pk=job_id)
    if not request.user.is_freelancer:
        return HttpResponseForbidden("Only freelancers can apply for jobs.")
    if job.employer_id == request.user.id:
        messages.error(request, "You cannot apply to your own job.")
        return redirect("job_detail", pk=job.pk)
    if job.status != Job.STATUS_OPEN:
        messages.error(request, "This job is no longer accepting applications.")
        return redirect("job_detail", pk=job.pk)
    if job.applications.filter(freelancer=request.user).exists():
        messages.info(request, "You have already applied to this job.")
        return redirect("job_detail", pk=job.pk)

    if request.method == "POST":
        form = ApplicationForm(request.POST)
        if form.is_valid():
            application = form.save(commit=False)
            application.job = job
            application.freelancer = request.user
            application.save()
            create_notification(
                job.employer,
                Notification.TYPE_APPLY,
                "New application received",
                f"{request.user.username} applied to your job '{job.title}'.",
                ref_type="job",
                ref_id=job.pk,
            )
            messages.success(request, "Application submitted successfully.")
            return redirect("job_detail", pk=job.pk)
    else:
        form = ApplicationForm()
    return render(request, "slowork/application_form.html", {"form": form, "job": job})


@login_required
@require_POST
def application_update_status(request, pk: int, action: str):
    application = get_object_or_404(
        Application.objects.select_related("job", "freelancer"),
        pk=pk,
        job__employer=request.user,
    )

    if action == "accept":
        with transaction.atomic():
            application.status = Application.STATUS_ACCEPTED
            application.save(update_fields=["status", "updated_at"])
            application.job.applications.exclude(pk=application.pk).update(status=Application.STATUS_REJECTED)
            job = application.job
            job.status = Job.STATUS_ASSIGNED
            job.selected_application = application
            job.save(update_fields=["status", "selected_application", "updated_at"])
        create_notification(
            application.freelancer,
            Notification.TYPE_STATUS,
            "Application accepted",
            f"You have been selected for '{application.job.title}'.",
            ref_type="job",
            ref_id=application.job.pk,
        )
        messages.success(request, "Freelancer accepted for this job.")
    elif action == "reject":
        application.status = Application.STATUS_REJECTED
        application.save(update_fields=["status", "updated_at"])
        create_notification(
            application.freelancer,
            Notification.TYPE_STATUS,
            "Application update",
            f"Your application for '{application.job.title}' was rejected.",
            ref_type="job",
            ref_id=application.job.pk,
        )
        messages.info(request, "Application marked as rejected.")
    else:
        messages.error(request, "Unsupported action.")
    return redirect("job_applications", pk=application.job.pk)


@login_required
@require_POST
def job_mark_completed(request, pk: int):
    job = get_object_or_404(Job, pk=pk, employer=request.user)
    job.status = Job.STATUS_COMPLETED
    job.save(update_fields=["status", "updated_at"])
    if job.selected_application:
        create_notification(
            job.selected_application.freelancer,
            Notification.TYPE_STATUS,
            "Job marked as completed",
            f"The employer marked '{job.title}' as completed.",
            ref_type="job",
            ref_id=job.pk,
        )
    messages.success(request, "Job marked as completed.")
    return redirect("job_detail", pk=job.pk)


@login_required
def work_submission_create(request, application_id: int):
    application = get_object_or_404(
        Application.objects.select_related("job", "freelancer"),
        pk=application_id,
    )
    job = application.job
    if application.freelancer != request.user:
        return HttpResponseForbidden("You can only submit work for your own applications.")
    if application.status != Application.STATUS_ACCEPTED:
        messages.error(request, "This application is not accepted yet.")
        return redirect("job_detail", pk=job.pk)

    if request.method == "POST":
        form = WorkSubmissionForm(request.POST)
        if form.is_valid():
            submission = form.save(commit=False)
            submission.application = application
            submission.job = job
            submission.submitted_by = request.user
            if application.submissions.filter(status=WorkSubmission.STATUS_CHANGES_REQUESTED).exists():
                submission.status = WorkSubmission.STATUS_RESUBMITTED
            else:
                submission.status = WorkSubmission.STATUS_SUBMITTED
            submission.save()
            job.status = Job.STATUS_SUBMITTED
            job.save(update_fields=["status", "updated_at"])
            create_notification(
                job.employer,
                Notification.TYPE_STATUS,
                "Work submitted",
                f"{request.user.username} submitted work for '{job.title}'.",
                ref_type="job",
                ref_id=job.pk,
            )
            messages.success(request, "Work submitted successfully.")
            return redirect("job_detail", pk=job.pk)
    else:
        form = WorkSubmissionForm()
    return render(
        request,
        "slowork/worksubmission_form.html",
        {"form": form, "application": application, "job": job},
    )


@login_required
@require_POST
def work_submission_update_status(request, submission_id: int, action: str):
    submission = get_object_or_404(
        WorkSubmission.objects.select_related("job", "submitted_by"),
        pk=submission_id,
        job__employer=request.user,
    )

    if action == "approve":
        submission.status = WorkSubmission.STATUS_APPROVED
        submission.save(update_fields=["status", "updated_at"])
        submission.job.status = Job.STATUS_COMPLETED
        submission.job.save(update_fields=["status", "updated_at"])
        create_notification(
            submission.submitted_by,
            Notification.TYPE_STATUS,
            "Submission approved",
            f"Your submission for '{submission.job.title}' was approved.",
            ref_type="job",
            ref_id=submission.job.pk,
        )
        messages.success(request, "Submission approved and job marked completed.")
    elif action == "request_changes":
        submission.status = WorkSubmission.STATUS_CHANGES_REQUESTED
        submission.save(update_fields=["status", "updated_at"])
        submission.job.status = Job.STATUS_IN_PROGRESS
        submission.job.save(update_fields=["status", "updated_at"])
        create_notification(
            submission.submitted_by,
            Notification.TYPE_STATUS,
            "Changes requested",
            f"Changes were requested for '{submission.job.title}'.",
            ref_type="submission",
            ref_id=submission.pk,
        )
        messages.info(request, "Requested changes from freelancer.")
    else:
        messages.error(request, "Unsupported action.")
    return redirect("job_detail", pk=submission.job.pk)


@login_required
def review_create(request, job_id: int, target: str):
    job = get_object_or_404(
        Job.objects.select_related("employer", "selected_application__freelancer"),
        pk=job_id,
    )
    if job.status != Job.STATUS_COMPLETED:
        messages.error(request, "Reviews are available after a job is completed.")
        return redirect("job_detail", pk=job.pk)

    if target == "freelancer":
        if job.employer != request.user:
            return HttpResponseForbidden("Only the employer can review the freelancer.")
        if not job.selected_application:
            messages.error(request, "No freelancer selected for this job.")
            return redirect("job_detail", pk=job.pk)
        reviewee = job.selected_application.freelancer
    elif target == "employer":
        if not request.user.is_freelancer:
            return HttpResponseForbidden("Only freelancers can review the employer.")
        if not job.selected_application or job.selected_application.freelancer != request.user:
            return HttpResponseForbidden("You did not work on this job.")
        reviewee = job.employer
    else:
        messages.error(request, "Unknown review target.")
        return redirect("job_detail", pk=job.pk)

    existing_review = Review.objects.filter(
        job=job,
        reviewer=request.user,
        reviewee=reviewee,
    ).first()
    if existing_review:
        messages.info(request, "You have already submitted a review.")
        return redirect("job_detail", pk=job.pk)

    if request.method == "POST":
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.job = job
            review.reviewer = request.user
            review.reviewee = reviewee
            review.save()
            create_notification(
                reviewee,
                Notification.TYPE_REVIEW,
                "New review received",
                f"{request.user.username} left you a review on '{job.title}'.",
                ref_type="job",
                ref_id=job.pk,
            )
            messages.success(request, "Review submitted. Thank you for the feedback!")
            return redirect("job_detail", pk=job.pk)
    else:
        form = ReviewForm()
    return render(
        request,
        "slowork/review_form.html",
        {"form": form, "job": job, "target": target, "reviewee": reviewee},
    )


@login_required
def notification_list(request):
    notifications = request.user.notifications.order_by("-created_at")
    if request.method == "POST":
        form = NotificationBulkUpdateForm(request.POST)
        if form.is_valid() and form.cleaned_data.get("mark_all_read"):
            notifications.filter(is_read=False).update(is_read=True)
            messages.success(request, "All notifications marked as read.")
            return redirect("notifications")
    else:
        form = NotificationBulkUpdateForm()
    return render(
        request,
        "slowork/notification_list.html",
        {"notifications": notifications, "form": form},
    )


@login_required
@require_POST
def notification_mark_read(request, pk: int):
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    notification.is_read = True
    notification.save(update_fields=["is_read"])
    next_url = request.POST.get("next") or "notifications"
    return redirect(next_url)
