#!/bin/bash
# 微信API服务启动脚本
echo "正在启动微信API服务..."

# 可以在下面设置API密钥或使用环境变量
# export API_KEY=your_secure_key_here

# 默认端口为8000，如需更改可修改以下命令的--port参数
python3 api_server.py --host 0.0.0.0 --port 8000 