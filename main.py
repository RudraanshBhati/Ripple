import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "backend.api.routes:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
    )
