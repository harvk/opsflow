from pydantic import (
    BaseModel,
)


class ServiceExistenceResponse(
    BaseModel
):
    """
    Internal Service Catalog existence response.
    """

    exists: bool