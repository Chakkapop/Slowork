from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.text import slugify
from decimal import Decimal, ROUND_HALF_UP
from django.db.models import Avg, Count

class User(AbstractUser):
    ROLE_EMPLOYER = "employer"
    ROLE_FREELANCER = "freelancer"
    ROLE_ADMIN = "admin"
    ROLE_CHOICES = [
        (ROLE_EMPLOYER, "Employer"),
        (ROLE_FREELANCER, "Freelancer"),
        (ROLE_ADMIN, "Admin"),
    ]

    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_FREELANCER)
    phone = models.CharField(max_length=20, blank=True, null=True)
    location_city = models.CharField(max_length=100, blank=True, null=True)
    rating_avg = models.DecimalField(max_digits=4, decimal_places=2, default=0)
    rating_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    profile_picture = models.ImageField(upload_to='profile_pictures/', null=True, blank=True)

    REQUIRED_FIELDS = ["email"]

    def save(self, *args, **kwargs):
        if self.role == self.ROLE_ADMIN and not self.is_staff:
            self.is_staff = True
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.username

    @property
    def is_employer(self) -> bool:
        return self.role == self.ROLE_EMPLOYER

    @property
    def is_freelancer(self) -> bool:
        return self.role == self.ROLE_FREELANCER

    @property
    def is_market_admin(self) -> bool:
        return self.role == self.ROLE_ADMIN

    @property
    def unread_notifications_count(self) -> int:
        return self.notifications.filter(is_read=False).count()


class JobCategory(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "job categories"

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while JobCategory.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                counter += 1
                slug = f"{base_slug}-{counter}"
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class Job(models.Model):
    STATUS_OPEN = "open"
    STATUS_ASSIGNED = "assigned"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_SUBMITTED = "submitted"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_OPEN, "Open"),
        (STATUS_ASSIGNED, "Assigned"),
        (STATUS_IN_PROGRESS, "In Progress"),
        (STATUS_SUBMITTED, "Submitted"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    employer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="jobs_posted",
        limit_choices_to={"role": User.ROLE_EMPLOYER},
    )
    category = models.ForeignKey(
        JobCategory,
        on_delete=models.PROTECT,
        related_name="jobs",
    )
    title = models.CharField(max_length=255)
    description = models.TextField()
    budget_min = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    budget_max = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    location_city = models.CharField(max_length=100, blank=True, null=True)
    deadline_date = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    selected_application = models.OneToOneField(
        "Application",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="awarded_job",
    )
    image = models.ImageField(upload_to='job_images/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.title


class Application(models.Model):
    STATUS_PENDING = "pending"
    STATUS_ACCEPTED = "accepted"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_ACCEPTED, "Accepted"),
        (STATUS_REJECTED, "Rejected"),
    ]

    job = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        related_name="applications",
    )
    freelancer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="applications",
        limit_choices_to={"role": User.ROLE_FREELANCER},
    )
    cover_message = models.TextField(blank=True, null=True)
    proposed_budget = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    proposed_days = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("job", "freelancer")

    def __str__(self) -> str:
        return f"{self.freelancer.username} -> {self.job.title}"


class WorkSubmission(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_SUBMITTED = "submitted"
    STATUS_RESUBMITTED = "resubmitted"
    STATUS_APPROVED = "approved"
    STATUS_CHANGES_REQUESTED = "changes_requested"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_SUBMITTED, "Submitted"),
        (STATUS_RESUBMITTED, "Resubmitted"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_CHANGES_REQUESTED, "Changes Requested"),
    ]

    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name="submissions",
    )
    job = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        related_name="submissions",
    )
    submitted_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="work_submissions",
    )
    text_notes = models.TextField(blank=True, null=True)
    change_request_reason = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Submission {self.pk} for {self.job.title}"


class SubmissionFile(models.Model):
    submission = models.ForeignKey(
        WorkSubmission,
        on_delete=models.CASCADE,
        related_name="files",
    )
    file = models.FileField(upload_to="file/",blank=True, null=True)
    file_url = models.URLField(max_length=500)
    original_name = models.CharField(max_length=255, blank=True, null=True)
    mime_type = models.CharField(max_length=100, blank=True, null=True)
    size_bytes = models.BigIntegerField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.original_name or self.file_url


class Review(models.Model):
    job = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    reviewer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="reviews_written",
    )
    reviewee = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="reviews_received",
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    comment = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["job", "reviewer", "reviewee"],
                name="unique_review_per_job_participants",
            ),
        ]

    def __str__(self) -> str:
        return f"Review {self.rating}/5 for {self.reviewee.username}"
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        user = self.reviewee
        stats = user.reviews_received.aggregate(avg=Avg("rating"), count=Count("id"))
        count = stats.get("count") or 0
        if count:
            user.rating_count = count
            user.rating_avg = Decimal(stats.get("avg") or 0).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        else:
            user.rating_count = 0
            user.rating_avg = 0
        user.save(update_fields=["rating_avg", "rating_count", "updated_at"])


class Notification(models.Model):
    TYPE_APPLY = "apply"
    TYPE_STATUS = "status"
    TYPE_REVIEW = "review"
    TYPE_SYSTEM = "system"
    TYPE_CHOICES = [
        (TYPE_APPLY, "Application"),
        (TYPE_STATUS, "Status"),
        (TYPE_REVIEW, "Review"),
        (TYPE_SYSTEM, "System"),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    ref_type = models.CharField(max_length=50, blank=True, null=True)
    ref_id = models.PositiveIntegerField(blank=True, null=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_read"]),
        ]

    def __str__(self) -> str:
        return f"{self.user.username}: {self.title}"
