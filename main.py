from fastapi import FastAPI
import uvicorn
import requests 

import base64
from io import BytesIO # 内存处理工具
from PIL import Image  # 图片处理工具

from pydantic import BaseModel # 用来定义接收的数据格式
import os
from openai import OpenAI


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
    return {"message": "Python后端(AI版)正在运行中！"}

# --- 初始化 AI 客户端 ---
# 从环境变量里读取 Key，如果在本地运行没有 Key，就设为 None
api_key = os.getenv("SILICON_KEY", None)

# 定义一个请求体结构，前端发来的数据必须包含 message
class ChatRequest(BaseModel):
    message:str

# --- 新增AI聊天接口 ---
@app.post("/chat")
def chat_with_ai(req: ChatRequest):
    if not api_key:
        return {
            "reply": "错误：后端没有配置API KEY，请在 Vercel 环境变量里添加 SILICON_KEY"
        }
    try:
        client=OpenAI(
            api_key=api_key,
            base_url="https://api.siliconflow.cn/v1"
        )
        
        response = client.chat.completions.create(
            model="deepseek-ai/DeepSeek-V3",
            messages=[
                {"role":"system","content":"你是一个幽默风趣的猫咪助手，说话喜欢带'喵'。"},
                {"role":"user","content":req.message}
            ],
            temperature=0.7,
        )
        
        ai_reply=response.choices[0].message.content
        return {"reply": ai_reply}
    
    except Exception as e:
        print("AI调用失败:", e)
        return {"reply": f"AI 累了，暂时无法回答喵... (错误: {str(e)})"}

# --- 原有的抓猫接口保持不变 ---
@app.get("/cat")
def get_cat():
    print("收到 Vue 的请求了！正在去帮它找猫...")

    try:
        # 发送请求时，带上 proxies 参数
        # timeout=10 意思是如果 10 秒还没连上，就放弃，别死等
        # 1.下载原图
        meta_response = requests.get("https://cataas.com/cat?json=true",timeout=10)
        meta_response.raise_for_status()   
        data=meta_response.json()
        
        img_url=data["url"]
        
        # 2. 【关键】Python 亲自把图片下载到内存里
        img_response = requests.get(img_url,timeout=10)
        
        # 3. 【核心优化】使用 Pillow 进行压缩
        # 打开图片
        image = Image.open(BytesIO(img_response.content))
        
        # A. 缩小尺寸：手机看图不需要太大，限制最大宽/高为 600px
        image.thumbnail((600, 600))
        
        # B. 格式统一：转为 JPEG (体积比 PNG 小很多)
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")
            
        # C. 降低质量：quality=60 (肉眼看不出区别，体积减半)
        buffer = BytesIO()
        image.save(buffer, format="JPEG", quality=60)
        
        # 4. 转 Base64 字符串
        img_str = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        return {
        "image":f"data:image/jpeg;base64,{img_str}",
        "note":"这是由Python后端代理获取的新猫猫（Vercel直连压缩版）"
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