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
