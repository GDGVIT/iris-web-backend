# DEPRECATED: This file is kept for backward compatibility
# New configuration is located in the config/ directory

import warnings
from config.base import BaseConfig

warnings.warn(
    "config.py is deprecated. Use configuration classes from config/ directory.",
    DeprecationWarning,
    stacklevel=2,
)

# Alias for backward compatibility
Config = BaseConfig
