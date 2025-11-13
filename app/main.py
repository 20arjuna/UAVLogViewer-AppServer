from fastapi import FastAPI
import uvicorn

app = FastAPI(
    title="UAV Log Viewer API",
    description="Backend API for UAV Log Viewer",
    version="1.0.0"
)

# -- Routes --
@app.get("/")
def read_root():
    return {"message": "Hello, World!"}

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.get("/api/v1/logs")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)