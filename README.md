# 天气查询 MCP 示例项目

这是一个基于 MCP (Model-Client-Provider) 架构的天气查询应用示例，展示了如何使用大型语言模型（LLM）与专用服务相结合，提供智能化的天气查询服务。

## 项目结构

- `server.py`: MCP 服务器，提供天气查询功能
- `client-3.py`: MCP 客户端，连接OpenAI和MCP服务器
- `.env.example`: 环境变量示例文件

## 功能特点

- 🤖 使用 OpenAI API 处理自然语言查询
- 🌤️ 通过 OpenWeather API 获取真实天气数据
- 🔌 基于 MCP 协议实现客户端-服务器通信
- 💬 用户友好的命令行交互界面
- 🛠️ 支持工具调用（Function Calling）自动化

## 安装步骤

1. 克隆本项目仓库

2. 安装依赖包
```bash
uv add openai httpx python-dotenv mcp
```

3. 配置环境变量
```bash
cp .env.example .env
```

4. 编辑 `.env` 文件，填入以下信息：
   - `OPENAI_API_KEY`: 你的 OpenAI API 密钥
   - `BASE_URL`: OpenAI API 基础 URL（可选）
   - `MODEL`: 要使用的 OpenAI 模型（如 "gpt-3.5-turbo"）
   - `OPENWEATHER_API_KEY`: 你的 OpenWeather API 密钥

5. 编辑 `server.py` 文件，使用你的 OpenWeather API 密钥替换 `API_KEY` 变量

## 使用方法

1. 启动客户端并连接服务器
```bash
uv run client-3.py server.py
```

2. 输入自然语言查询，例如：
   - "北京今天天气怎么样?"
   - "伦敦现在的温度是多少?"
   - "上海会下雨吗?"

3. 输入 `quit` 退出程序

## 工作原理

1. 客户端接收用户的自然语言查询
2. 客户端将查询发送给 OpenAI
3. OpenAI 分析查询意图，决定是否需要调用天气查询工具
4. 如果需要，客户端会调用服务器提供的天气查询工具
5. 服务器访问 OpenWeather API 获取天气数据
6. 结果返回给客户端，并由 OpenAI 格式化为自然语言回复
7. 客户端向用户展示最终结果

## 注意事项

- 需要有效的 OpenAI API 密钥和 OpenWeather API 密钥
- 该项目仅作为示例，可以根据需要进行扩展和修改

## 许可证

MIT
