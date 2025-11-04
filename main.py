import os
import shutil
import tempfile
import zipfile
import asyncio
from fastapi import FastAPI, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import geopandas as gpd

# 导入我们的数据库组件
from database import get_db, engine_sync

app = FastAPI(
    title="AI-WebGIS Platform API",
    version="1.0.0",
)


@app.get("/")
def read_root():
    return {"message": "欢迎来到 AI-WebGIS 平台 API！"}


@app.get("/db-test")
async def test_database_connection(db: AsyncSession = Depends(get_db)):
    """
    测试与 PostGIS 数据库的连接。
    """
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
        return {"status": "error", "message": "数据库连接失败", "error_details": str(e)}


@app.post("/upload_layer")
async def upload_layer(
        file: UploadFile = File(..., description="包含 Shapefile 的 .zip 压缩包"),
        layer_name: str = Form(..., description="要在数据库中创建的表名 (例如 'my_roads')"),
        db: AsyncSession = Depends(get_db)  # 注入异步 db，用于未来的元数据操作
):
    """
    上传一个 .zip 压缩的 Shapefile 并将其存入 PostGIS 数据库。
    """
    # 1. 验证文件类型
    if not file.filename.endswith('.zip'):
        raise HTTPException(status_code=400, detail="文件格式错误，请上传 .zip 压缩包。")

    # 2. 创建一个安全的临时目录来处理文件

    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # 3. 保存上传的 .zip 文件到临时目录
            temp_zip_path = os.path.join(temp_dir, file.filename)

            # 以 'wb' (写入-二进制) 模式打开文件
            with open(temp_zip_path, "wb") as f:
                # await file.read() 读取整个文件到内存
                f.write(await file.read())

            # 4. 解压缩 .zip 文件到同一个临时目录
            with zipfile.ZipFile(temp_zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)

            # 5. 在临时目录中查找 .shp 文件
            shp_path = None
            for item in os.listdir(temp_dir):
                if item.endswith(".shp"):
                    shp_path = os.path.join(temp_dir, item)
                    break

            if shp_path is None:
                raise HTTPException(status_code=400, detail=".zip 包中未找到 .shp 文件。")

            # 6. [核心] 使用 GeoPandas 读取 .shp 文件
            gdf = gpd.read_file(shp_path)

            # 7. (最佳实践) 统一坐标系 (CRS)
            # Web 地图的标准是 EPSG:4326 (WGS 84)
            if gdf.crs is None:
                print("警告：未设置 CRS。假设为 EPSG:4326")
            else:
                gdf = gdf.to_crs(epsg=4326)

            # 8. [核心] 将 GeoDataFrame 写入 PostGIS
            await asyncio.to_thread(
                gdf.to_postgis,
                layer_name,  # 用户指定的表名
                engine_sync,  # 使用我们的 *同步* 引擎
                if_exists='replace',  # 如果表已存在，则替换它 (方便测试)
                schema='public',  # 存入 public 模式
                index=True,  # 添加索引 (gid)
                index_label='gid'  # 索引列名
            )

            return {
                "status": "success",
                "message": f"图层 '{layer_name}' 已成功上传并存入数据库。",
                "features_count": len(gdf)
            }

        except Exception as e:
            # 捕获所有可能的错误 (解压失败, 读写失败, 数据库写入失败)
            raise HTTPException(status_code=500, detail=f"处理文件时发生错误: {str(e)}")

        # 临时目录 'temp_dir' 会在此处被自动删除
