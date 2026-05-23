import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "src.apps.admin_center.backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
