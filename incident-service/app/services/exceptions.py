class IncidentNotFoundError(Exception):
    """
    Raised when the requested Incident does not exist.
    """


class IncidentServiceReferenceError(Exception):
    """
    Raised when an Incident references an unknown catalog service.
    """


class ServiceCatalogUnavailableError(Exception):
    """
    Raised when Service Catalog validation cannot be performed.
    """