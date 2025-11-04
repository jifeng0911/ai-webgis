from fastapi import FastAPI, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from database import get_db, engine, Base


app = FastAPI(
    title="AI-WebGIS Platform API",
    version="1.0.0",
)


@app.get("/")
def read_root():

    return {"message": "欢迎来到 AI-WebGIS 平台 API！"}


@app.get("/hello")
def say_hello():
    return {"response": "Hello from FastAPI!"}



@app.get("/db-test")
async def test_database_connection(
    db: AsyncSession = Depends(get_db)
):

    try:

        query = text("SELECT PostGIS_full_version();")
        result = await db.execute(query)
        postgis_version = result.fetchone()

        if postgis_version:
            return {
                "status": "success",
                "message": "数据库连接成功！",
                "postgis_version": postgis_version[0]
            }
        else:
            return {"status": "error", "message": "已连接，但 PostGIS 版本查询失败"}

    except Exception as e:
        return {
            "status": "error",
            "message": "数据库连接失败",
            "error_details": str(e)
        }