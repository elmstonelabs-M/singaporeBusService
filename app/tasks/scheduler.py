from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.tasks.sync_lta_data import sync_all


def build_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="Asia/Singapore")
    scheduler.add_job(sync_all, "cron", day_of_week="wed", hour=3, minute=0)
    return scheduler
