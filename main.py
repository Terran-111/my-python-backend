from fastapi import FastAPI, Response # 引入 Response 对象手动控制
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool # 【关键】用于把脏活累活扔给线程池
from pydantic import BaseModel
import uvicorn
import os
import httpx # 请确保 requirements.txt 里有 httpx
import asyncio
from openai import AsyncOpenAI
from io import BytesIO
from PIL import Image
import base64

app = FastAPI()

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 独立的图片处理函数 (不要加 async) ---
# 这个函数负责 CPU 密集型工作：压缩图片
def process_image_sync(img_content):
    try:
        image = Image.open(BytesIO(img_content))
        image.thumbnail((1080, 1080)) # 缩小尺寸
        
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")
            
        buffer = BytesIO()
        image.save(buffer, format="JPEG", quality=85) # 压缩质量
        img_str = base64.b64encode(buffer.getvalue()).decode('utf-8')
        return img_str
    except Exception as e:
        print(f"图片处理出错: {e}")
        return None

@app.get("/")
def read_root():
    return {"message": "Python后端(异步+记忆版)正在运行！"}

# ==========================================
#  接口 1: 抓猫 (高并发异步版)
# ==========================================
@app.get("/cat")
async def get_cat():
    print("收到并发请求 -> 开始异步抓猫")
    # 伪装浏览器头，防止被反爬
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        # 使用 async with 自动管理连接开关
        async with httpx.AsyncClient(headers=headers, verify=False, timeout=10.0) as client:
            
            # A. 获取 JSON
            resp = await client.get("https://cataas.com/cat?json=true")
            if resp.status_code != 200:
                raise Exception(f"API报错: {resp.status_code}")
                
            data = resp.json()
            img_url = data.get("url")
            
            # URL 修复
            if img_url and not img_url.startswith("http"):
                img_url = f"https://cataas.com{img_url}"
            
            print(f"解析地址: {img_url}")

            # B. 下载图片二进制流
            img_resp = await client.get(img_url)
            if img_resp.status_code != 200:
                raise Exception("图片下载失败")
            
            img_content = img_resp.content

        # 2. 【关键一步】将 CPU 密集的图片压缩任务放入线程池
        # 这样即使图片处理慢，也不会卡住其他用户的请求！
        img_str = await run_in_threadpool(process_image_sync, img_content)
        
        if not img_str:
            raise Exception("图片压缩失败")

        # # 3. 构造返回数据
        # content = {
        #     "image": f"data:image/jpeg;base64,{img_str}",
        #     "note": "这是由 Python 异步高并发抓回来的新喵喵！"
        # }
        
        # # 4. 手动硬塞 CORS 头，防止浏览器拦截
        # response = JSONResponse(content=content)
        # response.headers["Access-Control-Allow-Origin"] = "*"
        # return response
        return {
            "image": f"data:image/jpeg;base64,{img_str}",
            "note": "这是由 Python 异步高并发抓回来的新喵喵！"
        }

    except Exception as e:
        # print(f"抓猫报错: {e}")
        # # 出错也要返回 JSON，并且带上 CORS 头，不然前端看不到报错信息
        # error_content = {
        #     "image": "",
        #     "note": f"抓猫失败: {str(e)}"
        # }
        # response = JSONResponse(content=error_content)
        # response.headers["Access-Control-Allow-Origin"] = "*"
        # return response
        print(f"抓猫报错: {e}")
        return {
            "image": "",
            "note": f"抓猫失败: {str(e)}"
        }


# ==========================================
#  接口 2: AI 聊天 (保持异步)
# ==========================================
class ChatRequest(BaseModel):
    history:list

api_key = os.getenv("SILICON_KEY", None)

@app.post("/chat")
async def chat_with_ai(req: ChatRequest):
    if not api_key:
        def error_gen(): yield "API Key 未设置，请检查环境变量 SILICON_KEY"
        return StreamingResponse(error_gen(), media_type="text/plain")
       
    client = AsyncOpenAI(
        api_key=api_key,
        base_url="https://api.siliconflow.cn/v1"
    )

    async def generate():
        try: 
            # 构造完整对话历史
            messages_to_send = [
                {"role": "system", "content": "你是一个傲娇又可爱的猫娘助手，每一句话结尾都要带'喵~'。你喜欢吃鱼，讨厌洗澡。"}
            ]
            # 再把前端发过来的历史记录接上去
            # 前端发来的格式是 [{"role": "user", "content": "..."}, ...]
            messages_to_send.extend(req.history)
            
            response = await client.chat.completions.create(
                model="deepseek-ai/DeepSeek-V3",
                messages=messages_to_send,
                temperature=0.7,
                stream=True
            )
            async for chunk in response:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            yield f"AI 出错啦: {str(e)}"

    return StreamingResponse(generate(), media_type="text/plain")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)