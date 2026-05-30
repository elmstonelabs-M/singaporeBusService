from app.tasks.scheduler import build_scheduler


def test_scheduler_runs_weekly_wednesday_3am_singapore() -> None:
    scheduler = build_scheduler()

    assert scheduler.timezone.key == "Asia/Singapore"
    assert len(scheduler.get_jobs()) == 1
    trigger = scheduler.get_jobs()[0].trigger
    assert str(trigger.fields[4]) == "wed"
    assert str(trigger.fields[5]) == "3"
    assert str(trigger.fields[6]) == "0"
