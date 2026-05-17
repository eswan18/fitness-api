from datetime import date

"""Default date bounds for API queries.

These defaults bound metrics and run queries when the client does not pass
explicit start/end dates.
"""

# This is roughly when I started tracking my runs.
DEFAULT_START = date(2016, 1, 1)
# Use date.max (not date.today()) so the upper bound doesn't freeze at the
# moment this module is imported — i.e. at pod startup. With date.today() the
# default end drifted into the past as the pod aged, silently filtering newly
# synced runs out of "all time" totals.
DEFAULT_END = date.max
