from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import Group
import os
from .models import (
    Application,
    Job,
    JobCategory,
    Review,
    User,
    WorkSubmission,
    SubmissionFile,
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


    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"].lower()
        role = self.cleaned_data["role"]
        user.role = role
        if commit:
            user.save()
            try:
                group = Group.objects.get(name=role)
                user.groups.add(group)
            except Group.DoesNotExist:
                pass
        return user
    

class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "phone", "location_city", "profile_picture", "bio", "skills", "portfolio_url")
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 4}),
            'skills': forms.Textarea(attrs={'rows': 2}),
        }

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
            "image",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = JobCategory.objects.order_by("name")
        self.fields["description"].widget = forms.Textarea(attrs={"rows": 5})

    def clean(self):
        cleaned_data = super().clean()
        budget_min = cleaned_data.get("budget_min")
        budget_max = cleaned_data.get("budget_max")
        if budget_min is not None and budget_max is not None and budget_min > budget_max:
            raise forms.ValidationError("Minimum budget cannot be higher than maximum budget.")
        return cleaned_data



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


class SubmissionFileForm(forms.ModelForm):
    class Meta:
        model = SubmissionFile
        fields = ("file",)

    def clean_file(self):
        file = self.cleaned_data.get('file', False)
        if file:
            file_size = file.size
            if file_size > 5 * 1024 * 1024: # 5 MB
                raise forms.ValidationError("ไฟล์มีขนาดใหญ่เกินไป (สูงสุด 5MB)")

            allowed_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.zip', '.rar']
            ext = os.path.splitext(file.name)[1].lower()
            if ext not in allowed_extensions:
                raise forms.ValidationError(f"ไม่อนุญาตให้อัปโหลดไฟล์ชนิด {ext}, อนุญาตเฉพาะ: {', '.join(allowed_extensions)}")

            return file

SubmissionFileFormSet = forms.modelformset_factory(
    SubmissionFile,
    form=SubmissionFileForm,
    extra=1, 
    can_delete=True 
)


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
