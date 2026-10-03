class CobsDecodeError(ValueError):
    """A frame isn't valid COBS: corrupted on the wire, or noise seen while syncing."""
