"""Entity models package.

Each model module must be imported here so that `Base.metadata` sees every
table before `init_database()` runs. Populated as each feature module
(Authentication, Farm, Cow, ...) is built.
"""
from models.cow import Cow, CowGender, HealthStatus, HornType, PregnancyStatus
from models.daily_record import DailyRecord
from models.farm import Farm, FarmEmployee
from models.milk_quality import MilkQualityTest, MilkSession, QualityGrade
from models.user import User, UserRole

__all__ = [
    "User",
    "UserRole",
    "Farm",
    "FarmEmployee",
    "Cow",
    "CowGender",
    "HornType",
    "PregnancyStatus",
    "HealthStatus",
    "DailyRecord",
    "MilkQualityTest",
    "MilkSession",
    "QualityGrade",
]
