"""Reproduce one immutable geometry bundle; no provider calls or DB writes."""
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from apps.pipeline.services.assembly_spec import make_assembly
from apps.pipeline.services.assembly_output import compile_bundle

class Command(BaseCommand):
    help = 'Build the Day 3 stepped display or original-brief refusal into a NEW directory.'

    def add_arguments(self, parser):
        parser.add_argument('--case', choices=['family-proposal','144','146'], default='family-proposal')
        parser.add_argument('--output', required=True)

    def handle(self,*args,**options):
        output=Path(options['output'])
        if output.exists():raise CommandError('Output already exists; immutable bundles are never overwritten.')
        try:record=compile_bundle(make_assembly(options['case']).model_dump(),output)
        except (ValueError,OSError) as exc:raise CommandError(str(exc)) from exc
        self.stdout.write(f"{record['preflight']['status']}: {output.resolve()} / {record['spec_hash']}")
