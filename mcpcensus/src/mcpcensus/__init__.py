"""mcpcensus - the MCP Observatory.

An anonymized sensor network over the Model Context Protocol ecosystem.
mcpaudit and mcpguard act as *sensors* (their ``--share`` flag emits a
privacy-engineered fingerprint); mcpcensus is the *observatory* that ingests,
aggregates, and publishes a monthly "State of MCP" report.
"""

__version__ = "0.1.0"

VERSION = __version__
"""Format identifier stamped into every fingerprint and aggregate."""

FORMAT = "mcpcensus/v1"
MIN_COHORT = 5
"""Default minimum cohort size below which published counts are suppressed."""

SALT_BYTES = 16
"""Per-device salt length for the stable-but-unlinkable device id."""

# Contract surface: what a *fingerprint* must provide, no matter the sensor.
FINGERPRINT_KEYS = ("format", "device", "submitted_at", "sensor", "axes")
SENSORS = ("context", "security")