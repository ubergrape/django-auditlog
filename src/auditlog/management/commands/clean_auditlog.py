from six import moves
from datetime import timedelta
import logging
from django.utils import timezone
from django.core.management.base import BaseCommand
from auditlog.models import LogEntry

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Cleans old log entries from the database.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days', type=int, help='days of logs from now to keep',
            required=True
        )
        parser.add_argument(
            '--force', action='store_true',
            help='don\'t ask for confirmation, instant delete.'
        )

    def handle(self, *args, **options):
        since = timezone.now() - timedelta(days=options['days'])
        logger.info('counting entries since %s...' % since.date())
        qs = LogEntry.objects.filter(timestamp__lte=since)
        cnt = qs.count()

        if options.get('force', None):
            qs.delete()

        answer = None if not options['force'] else 'y'

        while answer not in ['', 'y', 'n']:
            answer = moves.input(
                "%d objects are going to be deleted, "
                "shall I continue? [y/N]: " % cnt
            ).lower().strip()

        if answer == 'y':
            qs.delete()
            logger.info('all done, %d log entries deleted.' % cnt)
        else:
            logger.info('aborted.')
