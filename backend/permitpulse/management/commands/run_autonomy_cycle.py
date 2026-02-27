from __future__ import annotations

from django.core.management.base import BaseCommand

from permitpulse.services.runbook import record_slo_metrics, run_autonomous_recovery_cycle


class Command(BaseCommand):
    help = "Runs autonomous ops loop: SLO evaluation + automated recovery"

    def handle(self, *args, **options):
        metrics = record_slo_metrics()
        recovery = run_autonomous_recovery_cycle()
        self.stdout.write(self.style.SUCCESS(f"slo_metrics={len(metrics)} recovery={recovery}"))
