class ConfigError(ValueError):
    """receiver.toml is missing, malformed, or references something that can't be loaded."""
