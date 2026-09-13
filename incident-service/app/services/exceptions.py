class IncidentNotFoundError(Exception):
    """
    Raised when the requested Incident does not exist.
    """


class IncidentServiceReferenceError(Exception):
    """
    Raised when an Incident references an unknown catalog service.
    """