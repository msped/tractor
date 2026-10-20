"""
Management command to train a SpanCat model in this process.

Training is a batch job, not a queued task. Running it through django-q
imposes constraints that belong to the queue rather than to the work: a
per-task timeout that kills a long run partway, a broker that re-delivers
an unacknowledged task while it is still going, and worker processes that
have to be restarted to pick up a code change. A run started here has none
of those — it lives and dies with the terminal you start it in, and you can
see its output as it goes.

It also makes the machine a deployment choice rather than a code change:
anywhere with the repository, the virtualenv and access to the database and
media files can run this, which is the point if a laptop is the wrong place
for a multi-hour job.

The run still reports itself through TrainingControl, so it appears in the
UI and the Stop button works on it exactly as it would for a queued run.

Usage:
    python manage.py train_spancat
    python manage.py train_spancat --source both
    python manage.py train_spancat --max-span-tokens 48
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ...models import TrainingControl


class Command(BaseCommand):
    help = "Train a SpanCat model in this process, without a worker or queue."

    def add_arguments(self, parser):
        parser.add_argument(
            "--source",
            default="training_docs",
            choices=["training_docs", "redactions", "both"],
            help="Where training examples come from (default: training_docs).",
        )
        parser.add_argument(
            "--max-span-tokens",
            type=int,
            help=(
                "Override SPANCAT_MAX_SPAN_TOKENS for this run. Raising it "
                "covers longer annotations but grows peak memory sharply."
            ),
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help=(
                "Start even if a run is already recorded as in progress. "
                "Only for clearing a run that was killed outright."
            ),
        )

    def handle(self, *args, **options):
        from ...tasks import train_model

        if options["max_span_tokens"]:
            settings.SPANCAT_MAX_SPAN_TOKENS = options["max_span_tokens"]

        control = TrainingControl.get()
        if control.is_running and not options["force"]:
            raise CommandError(
                f"A training run is already in progress (pid {control.pid}, "
                f"started {control.started_at}). Stop it first, or pass "
                f"--force if you know it is dead."
            )
        if options["force"]:
            TrainingControl.objects.filter(pk=1).update(
                started_at=None, heartbeat_at=None, pid=None
            )
        if control.is_stale:
            self.stdout.write(
                self.style.WARNING(
                    f"Clearing an abandoned run (pid {control.pid}, last "
                    f"seen {control.heartbeat_at})."
                )
            )

        ceiling = getattr(settings, "SPANCAT_MAX_SPAN_TOKENS", 40)
        self.stdout.write(
            f"Training from {options['source']!r}, span ceiling {ceiling} "
            f"tokens. Ctrl-C to abandon, or use Stop in the UI."
        )

        train_model(source=options["source"])

        self.stdout.write(self.style.SUCCESS("Training finished."))
