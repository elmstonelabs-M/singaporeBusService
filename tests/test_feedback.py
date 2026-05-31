from sqlalchemy import select

from app.models.feedback import Feedback
from tests.conftest import FakeFeedbackEmailService


async def test_create_feedback_stores_and_sends_email(
    api_client,
    db_session,
    feedback_email_service: FakeFeedbackEmailService,
) -> None:
    response = await api_client.post(
        "/v1/feedback",
        json={
            "user_device_id": "device-feedback",
            "contact_email": "user@example.com",
            "category": "bug",
            "subject": "Arrival issue",
            "message": "Favorite list did not refresh.",
            "app_version": "1.0.0",
            "device_info": "Pixel 8 / Android 15",
        },
    )

    assert response.status_code == 201
    body = response.json()["data"]["feedback"]
    assert body["user_device_id"] == "device-feedback"
    assert body["email_status"] == "sent"
    assert len(feedback_email_service.sent_feedback_ids) == 1


async def test_create_feedback_marks_failed_when_email_send_fails(
    api_client,
    feedback_email_service: FakeFeedbackEmailService,
) -> None:
    feedback_email_service.should_fail = True

    response = await api_client.post(
        "/v1/feedback",
        json={
            "message": "The map marker is hard to tap.",
        },
    )

    assert response.status_code == 201
    body = response.json()["data"]["feedback"]
    assert body["email_status"] == "failed"


async def test_feedback_is_limited_to_six_per_client_id_per_day(
    api_client,
    db_session,
    feedback_email_service: FakeFeedbackEmailService,
) -> None:
    headers = {"x-forwarded-for": "203.0.113.10"}

    for index in range(6):
        response = await api_client.post(
            "/v1/feedback",
            headers=headers,
            json={
                "user_device_id": "device-1",
                "message": f"Feedback {index + 1}",
            },
        )
        assert response.status_code == 201

    blocked = await api_client.post(
        "/v1/feedback",
        headers=headers,
        json={
            "user_device_id": "device-1",
            "message": "Feedback 7",
        },
    )

    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "FEEDBACK_CLIENT_DAILY_LIMIT_EXCEEDED"
    assert len(feedback_email_service.sent_feedback_ids) == 6

    result = await db_session.execute(
        select(Feedback).where(Feedback.user_device_id == "device-1")
    )
    assert len(result.scalars().all()) == 6


async def test_feedback_allows_another_client_id_on_same_ip_before_ip_limit(
    api_client,
) -> None:
    headers = {"x-forwarded-for": "203.0.113.10"}

    for index in range(6):
        response = await api_client.post(
            "/v1/feedback",
            headers=headers,
            json={
                "user_device_id": "device-1",
                "message": f"Device 1 feedback {index + 1}",
            },
        )
        assert response.status_code == 201

    response = await api_client.post(
        "/v1/feedback",
        headers=headers,
        json={
            "user_device_id": "device-2",
            "message": "Device 2 feedback 1",
        },
    )

    assert response.status_code == 201


async def test_feedback_is_limited_by_ip_after_broader_network_threshold(
    api_client,
    feedback_email_service: FakeFeedbackEmailService,
) -> None:
    headers = {"x-forwarded-for": "203.0.113.10"}

    for index in range(18):
        response = await api_client.post(
            "/v1/feedback",
            headers=headers,
            json={
                "user_device_id": f"device-{index}",
                "message": f"Feedback {index + 1}",
            },
        )
        assert response.status_code == 201

    blocked = await api_client.post(
        "/v1/feedback",
        headers=headers,
        json={
            "user_device_id": "device-extra",
            "message": "Feedback 19",
        },
    )

    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "FEEDBACK_IP_DAILY_LIMIT_EXCEEDED"
    assert len(feedback_email_service.sent_feedback_ids) == 18
