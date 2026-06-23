# Compatibility shim — the new auth module supersedes this file.
# All code should import from auth.dependencies instead.
from auth.dependencies import get_current_user  # noqa: F401
