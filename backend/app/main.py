from fastapi import FastAPI

app = FastAPI(title="The Personal Morning Paper")


@app.get("/api/health")
def health():
    return {"ok": True}
