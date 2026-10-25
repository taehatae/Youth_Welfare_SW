"""Keep application imports during pytest away from the configured local DB."""

import os


os.environ["DATABASE_URL"] = "sqlite://"
