import asyncio
import os
import json
import sys
from typing import Optional, AsyncGenerator
from contextlib import AsyncExitStack
from openai import OpenAI
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# 加载 .env 文件，确保 API Key 受到保护
load_dotenv()

class MCPClient:
    def __init__(self):
        """初始化 MCP 客户端"""
        self.exit_stack = AsyncExitStack()
        self.openai_api_key = os.getenv("OPENAI_API_KEY")  # 读取 OpenAI API Key
        self.base_url = os.getenv("BASE_URL")  # 读取 BASE URL
        self.model = os.getenv("MODEL")  # 读取 model
        
        if not self.openai_api_key:
            raise ValueError("❌ 未找到 OpenAI API Key，请在 .env 文件中设置OPENAI_API_KEY")
        
        # 创建OpenAI client
        self.client = OpenAI(api_key=self.openai_api_key, base_url=self.base_url)
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
    
    async def connect_to_server(self, server_script_path: str):
        """连接到 MCP 服务器并列出可用工具"""
        is_python = server_script_path.endswith('.py')
        is_js = server_script_path.endswith('.js')
        if not (is_python or is_js):
            raise ValueError("服务器脚本必须是 .py 或 .js 文件")
        
        command = "python" if is_python else "node"
        server_params = StdioServerParameters(
            command=command,
            args=[server_script_path],
            env=None
        )
        
        # 启动 MCP 服务器并建立通信
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))
        await self.session.initialize()
        
        # 列出 MCP 服务器上的工具
        response = await self.session.list_tools()
        tools = response.tools
        print("\n已连接到服务器，支持以下工具:", [tool.name for tool in tools])
    
    async def process_query_stream(self, query: str) -> AsyncGenerator[str, None]:
        """
        流式处理用户查询并实时返回结果
        """
        messages = [{"role": "user", "content": query}]
        response = await self.session.list_tools()
        available_tools = [{
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.inputSchema
            }
        } for tool in response.tools]
        
        # 第一阶段：流式输出确定是否需要调用工具
        print("\n🤖 OpenAI: ", end="", flush=True)
        stream = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=available_tools,
            stream=True
        )
        
        collected_messages = []
        tool_calls = []
        finish_reason = None
        
        # 处理流式响应
        for chunk in stream:
            if not chunk.choices:
                continue
                
            choice = chunk.choices[0]
            finish_reason = choice.finish_reason
            
            # 处理工具调用
            if choice.delta.tool_calls:
                for tool_call_delta in choice.delta.tool_calls:
                    # 如果是新的工具调用
                    if tool_call_delta.index is not None and tool_call_delta.index >= len(tool_calls):
                        tool_calls.append({
                            "id": tool_call_delta.id or "",
                            "function": {
                                "name": tool_call_delta.function.name or "",
                                "arguments": tool_call_delta.function.arguments or ""
                            }
                        })
                    else:
                        # 添加到现有工具调用
                        if tool_call_delta.function.name:
                            tool_calls[tool_call_delta.index]["function"]["name"] += tool_call_delta.function.name
                        if tool_call_delta.function.arguments:
                            tool_calls[tool_call_delta.index]["function"]["arguments"] += tool_call_delta.function.arguments
                        if tool_call_delta.id:
                            tool_calls[tool_call_delta.index]["id"] = tool_call_delta.id
                continue
                
            # 处理文本内容
            if choice.delta.content:
                print(choice.delta.content, end="", flush=True)
                yield choice.delta.content
        
        # 如果是工具调用，则调用工具并返回结果
        if finish_reason == "tool_calls" and tool_calls:
            # 解析第一个工具调用
            tool_call = tool_calls[0]
            tool_name = tool_call["function"]["name"]
            try:
                tool_args = json.loads(tool_call["function"]["arguments"])
            except json.JSONDecodeError:
                print(f"\n\n⚠️ 工具参数解析错误: {tool_call['function']['arguments']}")
                yield f"\n\n⚠️ 工具参数解析错误"
                return
                
            # 输出调用信息
            print(f"\n\n[正在调用工具 {tool_name} 参数: {tool_args}]", flush=True)
            yield f"\n\n[正在调用工具 {tool_name}]"
            
            # 执行工具调用
            result = await self.session.call_tool(tool_name, tool_args)
            tool_result = result.content[0].text
            
            # 将工具调用和结果添加到消息中
            messages.append({
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": tool_call["id"],
                        "type": "function", 
                        "function": {"name": tool_name, "arguments": tool_call["function"]["arguments"]}
                    }
                ]
            })
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "content": tool_result
            })
            
            # 第二阶段：流式输出最终结果
            print("\n\n[工具返回结果]:\n", tool_result)
            print("\n\n🤖 OpenAI: ", end="", flush=True)
            
            final_stream = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True
            )
            
            for chunk in final_stream:
                if not chunk.choices:
                    continue
                    
                choice = chunk.choices[0]
                if choice.delta.content:
                    print(choice.delta.content, end="", flush=True)
                    yield choice.delta.content

    async def process_query(self, query: str) -> str:
        """使用流式API处理查询，但返回完整字符串结果"""
        result = ""
        async for chunk in self.process_query_stream(query):
            result += chunk
        return result
    
    async def chat_loop(self):
        """运行交互式聊天循环"""
        print("\n🤖 MCP 客户端已启动！输入 'quit' 退出")
        while True:
            try:
                query = input("\n你: ").strip()
                if query.lower() == 'quit':
                    break
                # 使用流式处理
                await self.process_query(query)
                print()  # 添加换行
            except Exception as e:
                print(f"\n⚠️ 发生错误: {str(e)}")
                import traceback
                traceback.print_exc()
    
    async def cleanup(self):
        """清理资源"""
        await self.exit_stack.aclose()

async def main():
    if len(sys.argv) < 2:
        print("Usage: python client.py <path_to_server_script>")
        sys.exit(1)
    
    client = MCPClient()
    try:
        await client.connect_to_server(sys.argv[1])
        await client.chat_loop()
    finally:
        await client.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
