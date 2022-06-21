import datetime

import dateutil.parser


def string_to_datetime(datetime_str: str, max_year=5000, **kwargs) -> datetime.datetime:
    """Convert a string into a datetime. `datetime_str` can be one of the following

        * A year (eg. '2025')
        * A unix timestamp (in seconds) (eg. '1626684322')
        * A `dateutil` parsable string

    :param max_year: int. The cutoff for when a `datestime_str` representing a single integer is
        interpreted as a year or as a unix timestamp
    :param kwargs: Additional parameters passed directly into the `dateutil.parser` to customize
        parsing. For example `dayfirst=True`.

    """
    try:
        datetime_as_int = int(datetime_str)
    except ValueError:
        return dateutil.parser.parse(datetime_str, **kwargs)
    else:
        if datetime_as_int <= max_year:
            return datetime.datetime(datetime_as_int, month=1, day=1)
        return datetime.datetime.fromtimestamp(datetime_as_int)
