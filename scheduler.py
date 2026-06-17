"""한국시간(KST) 10~19시 매시 정각에 수집 실행."""
import traceback

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from collector import KST
from run_once import run_once


def _job():
    try:
        run_once()
    except Exception:
        traceback.print_exc()


def main():
    sched = BlockingScheduler(timezone=KST)
    sched.add_job(_job, CronTrigger(hour="10-19", minute=0, timezone=KST),
                  id="collect", max_instances=1, misfire_grace_time=600)
    print("스케줄러 시작: KST 10:00~19:00 매시 정각. (Ctrl+C 종료)")
    _job()  # 시작 즉시 1회
    try:
        sched.start()
    except (KeyboardInterrupt, SystemExit):
        print("종료")


if __name__ == "__main__":
    main()
