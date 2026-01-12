from datetime import date

"""Default date bounds for API queries.

These defaults bound metrics and run queries when the client does not pass
explicit start/end dates.
"""

# This is roughly when I started tracking my runs.
DEFAULT_START = date(2016, 1, 1)
DEFAULT_END = date.today()
