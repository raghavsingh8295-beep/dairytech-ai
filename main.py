"""trimTAB entry point."""
from __future__ import annotations

from database.init_db import init_database
from ui.app import DairyTechApp
from utils.logger import get_logger

logger = get_logger("main")


def main() -> None:
    logger.info("Starting trimTAB...")
    init_database()

    app = DairyTechApp()
    app.mainloop()

    logger.info("trimTAB closed.")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.exception("Fatal error during startup.")
        raise
