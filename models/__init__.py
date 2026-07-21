"""Entity models package.

Each model module must be imported here so that `Base.metadata` sees every
table before `init_database()` runs. Populated as each feature module
(Authentication, Farm, Cow, ...) is built.
"""
from models.user import User, UserRole

__all__ = ["User", "UserRole"]
