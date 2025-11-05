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
        db: AsyncSession = Depends(get_db)
):

    print("\n--- [!!] 开始处理 /upload_layer 请求 ---")  # [DEBUG]

    # 1. 验证文件类型
    if not file.filename.endswith('.zip'):
        print(f"错误: 文件名 '{file.filename}' 不是 .zip。")  # [DEBUG]
        raise HTTPException(status_code=400, detail="文件格式错误，请上传 .zip 压缩包。")

    # 2. 创建一个安全的临时目录来处理文件
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"  [1] 临时目录已创建: {temp_dir}")  # [DEBUG]
        try:
            # 3. 保存上传的 .zip 文件到临时目录
            temp_zip_path = os.path.join(temp_dir, file.filename)
            print(f"  [2] 准备保存 .zip 文件到: {temp_zip_path}")  # [DEBUG]

            with open(temp_zip_path, "wb") as f:
                f.write(await file.read())

            print(f"  [3] .zip 文件已保存。")  # [DEBUG]

            # 4. 解压缩 .zip 文件到同一个临时目录
            print(f"  [4] 正在解压缩 .zip 文件...")  # [DEBUG]
            with zipfile.ZipFile(temp_zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)

            print(f"  [5] 解压完成。开始 *递归* 搜索 .shp 文件...")  # [DEBUG]

            # 5. [终极调试版] 递归查找 .shp 文件
            shp_path = None

            # --- 详细打印 os.walk 的每一步 ---
            for root, dirs, files in os.walk(temp_dir):
                print(f"\n    > 正在扫描目录: {root}")  # [DEBUG]

                if dirs:
                    print(f"    > 发现子目录: {dirs}")  # [DEBUG]
                if not files:
                    print("    > (此目录中没有文件)")  # [DEBUG]

                for filename in files:
                    print(f"    > 发现文件: {filename}")  # [DEBUG]

                    # 检查文件名是否以 .shp 结尾
                    if filename.endswith(".shp"):
                        shp_path = os.path.join(root, filename)
                        print(f"    > [!!] 匹配成功！.shp 文件是: {shp_path}")  # [DEBUG]
                        break  # 找到第一个就停止

                if shp_path:  # 如果在内层循环找到了，也跳出外层循环
                    break
            # --- 调试结束 ---

            if shp_path is None:
                print("  [!!] 错误: 递归搜索完成，但未找到 .shp 文件。")  # [DEBUG]
                raise HTTPException(status_code=400, detail=".zip 包中未找到 .shp 文件 (已递归搜索)。")

            # 6. [核心] 使用 GeoPandas 读取 .shp 文件
            print(f"  [6] 正在使用 GeoPandas 读取: {shp_path}...")
            gdf = gpd.read_file(shp_path)

            # 7. (最佳实践) 统一坐标系 (CRS)
            print(f"  [7] 原始坐标系: {gdf.crs}")
            if gdf.crs is None:

                print("    > 警告: 原始CRS为 'None'。将 *假设* 其为 EPSG:4326。")
                gdf.crs = "EPSG:4326"
            else:
                print(f"    > 正在将 CRS 从 {gdf.crs} *转换* 为 EPSG:4326...")
                gdf = gdf.to_crs(epsg=4326)

            # 8. [核心] 将 GeoDataFrame 写入 PostGIS
            print(f"  [8] 正在将 {len(gdf)} 个要素写入数据库表: {layer_name} (同步线程)...")
            await asyncio.to_thread(
                gdf.to_postgis,
                layer_name,
                engine_sync,
                if_exists='replace',
                schema='public',
                index=True,
                index_label='gid'
            )

            print("  [9] 数据写入成功。")
            print("--- [!!] 请求处理完毕 ---")  # [DEBUG]

            return {
                "status": "success",
                "message": f"图层 '{layer_name}' 已成功上传并存入数据库。",
                "features_count": len(gdf)
            }

        except zipfile.BadZipFile as e:
            print(f"  [!!] 致命错误: 文件不是一个有效的 .zip 文件。可能是 .rar 或已损坏。 错误: {e}")  # [DEBUG]
            raise HTTPException(status_code=400,
                                detail=f"解压失败：文件不是一个有效的 .zip 文件。请不要上传 .rar 文件。错误: {e}")

        except Exception as e:
            print(f"  [!!] 发生未捕获的错误: {str(e)}")  # [DEBUG]
            raise HTTPException(status_code=500, detail=f"处理文件时发生未知错误: {str(e)}")

