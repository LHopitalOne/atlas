import argparse

from reminder_cron.job import ReminderJob
from reminder_cron.settings import Settings


def main() -> None:
    parser = argparse.ArgumentParser(prog="reminder-cron")
    parser.add_argument("--once", action="store_true", help="run a single sweep and exit")
    args = parser.parse_args()

    job = ReminderJob(Settings.from_env())
    try:
        if args.once:
            job.run_once()
        else:
            job.run_forever()
    finally:
        job.close()


if __name__ == "__main__":
    main()
