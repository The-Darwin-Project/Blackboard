from fastapi import FastAPI
app = FastAPI(title="Darwin BlackBoard")
@app.get("/")
def health(): return {"status": "brain_online"}
