from fastapi import FastAPI
import uvicorn
import aiohttp  # 1. 引入异步请求库 aiohttp
import asyncio  # 引入 asyncio
import base64
from io import BytesIO
from PIL import Image
from pydantic import BaseModel
import os
from openai import AsyncOpenAI  # 2. 引入异步的 OpenAI 客户端
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.get("/")
def read_root():
    return {"message": "Python后端(AI版 - 异步高性能模式)正在运行中！"}

# --- 初始化 AI 客户端 ---
api_key = os.getenv("SILICON_KEY", None)

class ChatRequest(BaseModel):
    message: str

# --- 3. 异步 AI 聊天接口优化 ---
@app.post("/chat")
async def chat_with_ai(req: ChatRequest):
    if not api_key:
        return {"reply": "错误：后端没有配置API KEY"}

    # 使用 AsyncOpenAI 而不是 OpenAI
    client = AsyncOpenAI(
        api_key=api_key,
        base_url="https://api.siliconflow.cn/v1"
    )

    async def generate():
        try:
            # 这里加上了 await，且 create 方法是异步的
            response = await client.chat.completions.create(
                model="deepseek-ai/DeepSeek-V3",
                messages=[
                    {"role": "system", "content": "你是一个风趣的猫娘助手，说话结尾喜欢带'喵'。"},
                    {"role": "user", "content": req.message}
                ],
                temperature=0.7,
                stream=True
            )
            
            # 异步循环读取流
            async for chunk in response:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            yield f'出错了喵：{str(e)}'

    return StreamingResponse(generate(), media_type="text/plain")


# --- 4. 异步抓猫接口优化 ---
@app.get("/cat")
async def get_cat(): # 注意这里变成了 async def
    print("收到 Vue 的请求了！正在去帮它找猫...")

    try:
        # 创建一个异步的 session
        async with aiohttp.ClientSession() as session:
            # 1. 异步下载 JSON 数据
            # 这里的 await 意味着：在等网络响应时，CPU可以去处理别人的请求
            async with session.get("https://cataas.com/cat?json=true", timeout=10) as resp:
                resp.raise_for_status()
                data = await resp.json()
                img_url = data.get("url")
                # 【核心修复】如果 API 返回的是相对路径（例如 /cat/xxx），我们需要加上域名
                if img_url and not img_url.startswith("http"):
                    img_url = f"https://cataas.com{img_url}"
                
                print(f"解析到的图片地址: {img_url}") # 打印出来方便调试

            # 2. 异步下载图片二进制数据
            async with session.get(img_url, timeout=10) as img_resp:
                img_content = await img_resp.read() # 获取二进制内容

        # 3. 图片压缩处理 (Pillow 处理是 CPU 密集型，通常很快，可以直接写在这里)
        # 如果图片处理非常慢，需要放到 run_in_executor 线程池中，但一般抓猫图不需要
        image = Image.open(BytesIO(img_content))
        image.thumbnail((600, 600))

        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")

        buffer = BytesIO()
        image.save(buffer, format="JPEG", quality=60)
        
        img_str = base64.b64encode(buffer.getvalue()).decode('utf-8')

        return {
            "image": f"data:image/jpeg;base64,{img_str}",
            "note": "这是由Python后端代理获取的新猫猫（异步加速版）"
        }

    except Exception as e:
        print("抓猫失败:", e)
        return {
            "image": "",
            "note": f"抓猫失败了，原因: {str(e)}"
        }

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)