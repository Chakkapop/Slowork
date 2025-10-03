from collections.abc import Iterable
from typing import Optional

from django.db import transaction

from .models import Notification, User


def create_notification(
    user: Optional[User],
    notif_type: str,
    title: str,
    message: str,
    *,
    ref_type: str | None = None,
    ref_id: int | None = None,
) -> Notification | None:
    if user is None:
        return None
    with transaction.atomic():
        notification = Notification.objects.create(
            user=user,
            type=notif_type,
            title=title,
            message=message,
            ref_type=ref_type,
            ref_id=ref_id,
        )
    return notification


def notify_users(
    users: Iterable[User],
    notif_type: str,
    title: str,
    message: str,
    *,
    ref_type: str | None = None,
    ref_id: int | None = None,
) -> list[Notification]:
    notifications: list[Notification] = []
    for user in users:
        notification = create_notification(
            user,
            notif_type,
            title,
            message,
            ref_type=ref_type,
            ref_id=ref_id,
        )
        if notification:
            notifications.append(notification)
    return notifications
