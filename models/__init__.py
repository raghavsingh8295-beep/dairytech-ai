"""Entity models package.

Each model module must be imported here so that `Base.metadata` sees every
table before `init_database()` runs. Populated as each feature module
(Authentication, Farm, Cow, ...) is built.
"""
from models.breeding import CalfBirth, CalfOutcome, HeatCycle, Insemination, PregnancyCheck, PregnancyResult
from models.cow import Cow, CowGender, HealthStatus, HornType, PregnancyStatus
from models.daily_record import DailyRecord
from models.farm import Farm, FarmEmployee
from models.health import Disease, DiseaseSeverity, DiseaseStatus, DoctorVisit, Treatment, Vaccination
from models.inventory import InventoryCategory, InventoryItem, MovementType, StockMovement, Supplier
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
    "Disease",
    "DiseaseSeverity",
    "DiseaseStatus",
    "Vaccination",
    "Treatment",
    "DoctorVisit",
    "HeatCycle",
    "Insemination",
    "PregnancyCheck",
    "PregnancyResult",
    "CalfBirth",
    "CalfOutcome",
    "Supplier",
    "InventoryItem",
    "InventoryCategory",
    "StockMovement",
    "MovementType",
]
