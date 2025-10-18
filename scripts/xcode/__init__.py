"""
Xcode build automation module.

Provides structured, modular access to xcodebuild and xcresult functionality.
"""

from .cache import XCResultCache
from .xcresult import XCResultParser
from .reporter import OutputFormatter
from .builder import BuildRunner

__all__ = [
    'XCResultCache',
    'XCResultParser',
    'OutputFormatter',
    'BuildRunner'
]
