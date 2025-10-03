from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import (
    Application,
    Job,
    JobCategory,
    Review,
    User,
    WorkSubmission,
)


class UserRegistrationForm(UserCreationForm):
    role = forms.ChoiceField(
        choices=[
            (User.ROLE_EMPLOYER, "Employer"),
            (User.ROLE_FREELANCER, "Freelancer"),
        ],
        label="Account type",
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "first_name", "last_name", "role")

    def clean_role(self):
        role = self.cleaned_data["role"]
        if role not in {User.ROLE_EMPLOYER, User.ROLE_FREELANCER}:
            raise forms.ValidationError("Please choose a valid role.")
        return role

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"].lower()
        user.role = self.cleaned_data["role"]
        if commit:
            user.save()
        return user


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "phone", "location_city")


class JobForm(forms.ModelForm):
    deadline_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )

    class Meta:
        model = Job
        fields = (
            "category",
            "title",
            "description",
            "budget_min",
            "budget_max",
            "location_city",
            "deadline_date",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = JobCategory.objects.order_by("name")
        self.fields["description"].widget = forms.Textarea(attrs={"rows": 5})

    def clean(self):
        cleaned = super().clean()
        budget_min = cleaned.get("budget_min")
        budget_max = cleaned.get("budget_max")
        if budget_min is not None and budget_max is not None and budget_min > budget_max:
            raise forms.ValidationError("Minimum budget cannot be higher than maximum budget.")
        return cleaned


class JobFilterForm(forms.Form):
    search = forms.CharField(required=False, label="Search")
    category = forms.ModelChoiceField(
        queryset=JobCategory.objects.none(),
        required=False,
        empty_label="All categories",
    )
    status = forms.ChoiceField(
        required=False,
        choices=[("", "All statuses")] + list(Job.STATUS_CHOICES),
    )
    posted = forms.ChoiceField(
        required=False,
        choices=[
            ("", "Any time"),
            ("1", "Last 24 hours"),
            ("7", "Last 7 days"),
            ("30", "Last 30 days"),
        ],
        label="Posted",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = JobCategory.objects.order_by("name")


class ApplicationForm(forms.ModelForm):
    class Meta:
        model = Application
        fields = ("cover_message", "proposed_budget", "proposed_days")
        widgets = {
            "cover_message": forms.Textarea(attrs={"rows": 4}),
        }


class WorkSubmissionForm(forms.ModelForm):
    class Meta:
        model = WorkSubmission
        fields = ("text_notes",)
        widgets = {
            "text_notes": forms.Textarea(attrs={"rows": 4}),
        }


class ReviewForm(forms.ModelForm):
    rating = forms.IntegerField(
        min_value=1,
        max_value=5,
        help_text="Give a rating between 1 (lowest) and 5 (highest)",
    )

    class Meta:
        model = Review
        fields = ("rating", "comment")
        widgets = {
            "comment": forms.Textarea(attrs={"rows": 4}),
        }


class NotificationBulkUpdateForm(forms.Form):
    mark_all_read = forms.BooleanField(required=False, initial=True)
