from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Avg, Count
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Review


@receiver(post_save, sender=Review)
def update_reviewee_rating(sender, instance: Review, **_kwargs) -> None:
    """Recalculate the aggregate rating whenever a review is saved."""
    user = instance.reviewee
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
