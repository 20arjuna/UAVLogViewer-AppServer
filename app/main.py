from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import json
import uuid
import uvicorn

# Create tmp directory in the repo
BASE_DIR = Path(__file__).parent.parent  # UAVLogViewer-AppServer/
TMP_DIR = BASE_DIR / "tmp" / "uav_logs"
TMP_DIR.mkdir(parents=True, exist_ok=True)


app = FastAPI(
    title="UAV Log Viewer API",
    description="Backend API for UAV Log Viewer",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_methods=["*"],
    allow_headers=["*"],
)

# -- Routes --
@app.get("/")
def read_root():
    return {"message": "Hello, World!"}

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.post("/upload")
def save_data(data: dict = Body(...)):
    file_id = str(uuid.uuid4())
    
    # Save to file in repo's tmp directory
    filepath = TMP_DIR / f"{file_id}.json"
    filepath.write_text(json.dumps(data))
    
    print(f"✅ Saved to {filepath}")
    
    return {"file_id": file_id, "status": "saved", "path": str(filepath)}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)