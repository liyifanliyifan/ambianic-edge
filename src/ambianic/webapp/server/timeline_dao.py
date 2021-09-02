"""REST API for timeline events fired by pipelines."""
import logging
import os
from datetime import datetime
from pathlib import Path

import yaml

log = logging.getLogger()


def _remove_timeline(file_path):
    try:
        os.remove(file_path)
    except Exception:
        logging.exception("Error removing %s" % file_path)


def get_timeline(before_datetime=None, page=1, data_dir=None):
    """Get stored pipeline timeline events.

    :Parameters:
    ----------
    before_datetime : date time in ISO 8601 compatible format,
        YYYY-MM-DDTHH:MM:SS. For example '2002-12-25 00:00:00-06:39'.
        It uses python's standard function datetime.fromisoformat().
        If not provided, the function will start with the most recent available
        sample.
    page : positive integer
        Paginates samples in batches of 5. Defaults to page=1.

    :Returns:
    -------
    list: json
        Returns a list of previously saved pipeline events.

    """

    if data_dir is None or not os.path.exists(data_dir):
        log.warning("data_dir is not valid: %s", data_dir)
        return []

    parsed_datetime = None
    assert isinstance(page, int)
    assert page > 0
    page_size = 5
    if before_datetime:
        try:
            parsed_datetime = datetime.fromisoformat(before_datetime)
            log.debug("Fetching samples saved before %s", parsed_datetime)
        except ValueError as e:
            log.warning(
                "Unable to parse before_datetime parameter: %s. " " Error: %s",
                before_datetime,
                str(e),
            )
    page_start_position = (page - 1) * page_size
    page_end_position = page_start_position + page_size

    if not parsed_datetime:
        log.debug("Fetching most recent saved samples")
    log.debug(
        "Fetching samples page %d. Page size %d. " "Sample index range [%d:%d]. ",
        page,
        page_size,
        page_start_position,
        page_end_position,
    )

    files = list(Path(data_dir).glob("./timeline-event-log.yaml*"))
    files = sorted(files, reverse=False)

    page_count = 1
    events_queue = []

    # load the event history, older first
    for file_path in files:
        with file_path.open() as pf:

            try:
                timeline_events = yaml.safe_load(pf)
                timeline_events += events_queue
            except (
                yaml.reader.ReaderError,
                yaml.scanner.ScannerError,
                yaml.composer.ComposerError,
                yaml.constructor.ConstructorError,
            ):
                log.exception("Detected unreadable timeline, removing %s" % file_path)
                _remove_timeline(file_path)
                continue

            events_queue = []
            events_len = len(timeline_events)
            if events_len < page_end_position:

                pages_mod = events_len % page_size
                if pages_mod > 0:
                    events_queue = timeline_events[0:pages_mod]
                    page_start_position += pages_mod
                    page_end_position += pages_mod

                page_start_position -= events_len
                page_end_position -= events_len
                page_count += 1

            else:

                if page_start_position >= events_len:
                    return []

                # events are appended to the file as they arrive
                # we need to read in reverse order to get the latest one first

                return timeline_events[
                    -1 * page_start_position - 1 : -1 * page_end_position - 1 : -1
                ]

    page_count += 1

    if page_count < page:
        return []

    # return the remaining queue if there are no more files to process
    return events_queue
