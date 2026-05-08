import uvicorn
from src.core.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "src.apps.dashboard:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=True,
        log_level="warning",
    )
