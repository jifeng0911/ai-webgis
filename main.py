from fastapi import FastAPI

app = FastAPI(
    title = "AI-WebGIS",
    version = "1.0.0"
)
@app.get('/')
def read_root():
    return {"message":"欢迎来到AI—web GIS平台"}
@app.get('/hello')
def say_hello():
    return {"response":"Hello,From FastAPI"}