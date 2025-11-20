from fastapi import FastAPI
import uvicorn
import requests 

# 1. 创建一个 App 实例
app = FastAPI()

# 允许跨域的代码（为了让Vue能访问Python后端）
from fastapi.middleware.cors import CORSMiddleware #  导入FastAPI中的CORS中间件
app.add_middleware( #  为FastAPI应用添加CORS中间件配置
    CORSMiddleware, #  指定使用CORSMiddleware中间件
    allow_origins=["*"], #  允许所有来源的跨域请求
    allow_methods=["*"], #  允许所有HTTP方法
    allow_headers=["*"] #  允许所有请求头
)

# 2. 定义一个接口 (API)
# 当别人访问根目录 "/" 时，执行下面的函数
@app.get("/")
def read_root():
    return {"message": "Python后端正在运行中！"}

# 3. 定义另一个接口：/cat
@app.get("/cat")
def get_cat():
    print("收到 Vue 的请求了！正在去帮它找猫...")
    # 1. 设置代理 (假设你的梯子端口是 7890)
    # 如果你的端口不是 7890，记得改这里！
    my_proxies = {
        "http": "http://127.0.0.1:7890",
        "https": "http://127.0.0.1:7890",
    }
    try:
        # 2. 发送请求时，带上 proxies 参数
        # timeout=10 意思是如果 10 秒还没连上，就放弃，别死等
        response = requests.get("https://cataas.com/cat?json=true",proxies=my_proxies,timeout=10)
        data=response.json()
        real_url=data["url"]
        return {
        "image":real_url,
        "note":"这是由Python后端代理获取的新猫猫"
        }
    except Exception as e:
        print("抓猫失败:", e)
        return {
            "image": "", # 返回空图片
            "note": f"抓猫失败了，原因: {str(e)}" 
        }

# 4. 让代码可以直接运行
if __name__ == "__main__":
    # main:app 模块名：应用实例名
    # host="0.0.0.0" 代表允许任何设备访问
    # port=8000 是后端常用的端口
    # reload=True 代表改了代码自动重启，不用手动关了再开
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)