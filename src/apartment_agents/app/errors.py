class ApartmentAgentsError(Exception):
    """Base application error."""


class StartupValidationError(ApartmentAgentsError):
    """Raised when application startup validation fails."""


class ServiceValidationError(ApartmentAgentsError):
    """Raised when a service request fails validation."""


class MissingListingUrlError(ServiceValidationError):
    """Raised when an analysis request omits the listing URL."""


class MissingBuyerProfileIdError(ServiceValidationError):
    """Raised when an analysis request omits the buyer profile identifier."""


class ConfigValidationError(ApartmentAgentsError):
    """Raised when runtime configuration is invalid."""


class ListingIngestionError(ApartmentAgentsError):
    """Raised when listing ingestion fails."""


class ListingFetchError(ListingIngestionError):
    """Raised when a live listing page cannot be fetched."""


class ListingFetchBlockedError(ListingFetchError):
    """Raised when a listing page is blocked by anti-bot protection."""


class UnsupportedListingDomainError(ListingIngestionError):
    """Raised when a listing URL domain is not supported."""


class FixtureNotFoundError(ApartmentAgentsError):
    """Raised when a required fixture is missing."""


class BuyerProfileNotFoundError(FixtureNotFoundError):
    """Raised when a buyer fixture is missing."""


class MarketSnapshotNotFoundError(FixtureNotFoundError):
    """Raised when a market snapshot fixture is missing."""


class AdkRuntimeUnavailableError(ApartmentAgentsError):
    """Raised when an ADK-backed runtime is requested but unavailable."""


class ReportWriteError(ApartmentAgentsError):
    """Raised when a rendered report cannot be written."""


class WorkspacePersistenceError(ApartmentAgentsError):
    """Raised when local workspace state cannot be saved or loaded."""
