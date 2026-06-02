"""API2Agent package."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("api2agent")
except PackageNotFoundError:
    __version__ = "0.1.0rc2"

from api2agent.sdk import call

__all__ = ["__version__", "call"]
