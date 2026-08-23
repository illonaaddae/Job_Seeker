"""Job discovery sources.

Each source turns some remote system into a list of `Job` objects with a real
description attached. Descriptions matter more than volume: a job you cannot
read is a job you cannot tailor an application to.
"""

from .base import Source, SourceError, registry
from . import aggregators, ashby, exa, greenhouse, lever, manual, workable  # noqa: F401

__all__ = ["Source", "SourceError", "registry"]
