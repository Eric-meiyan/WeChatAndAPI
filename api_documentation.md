# 微信API服务使用文档

## 概述

微信API服务提供了访问微信联系人、聊天记录、账号信息等功能的HTTP接口。通过这些API，可以方便地集成微信数据到您的应用程序中。

## 使用前准备

1. 安装依赖库：
   ```
   pip install -r requirements.txt
   ```

2. 启动API服务：
   - Windows系统: 双击运行 `start_api_server.bat` 或在命令行运行 `python api_server.py`
   - Linux/Mac系统: 在终端运行 `./start_api_server.sh` 或 `python3 api_server.py`

3. 默认端口为8000，API文档访问地址: http://localhost:8000/docs

## 安全认证

所有API请求都需要通过API密钥进行认证。请在请求头中加入 `X-API-Key` 字段，值为您设置的API密钥。

默认API密钥为代码中设置的值，建议在生产环境中更改为自定义密钥。
可以通过以下方式设置API密钥：
- 环境变量: `API_KEY=your_secure_key_here`
- 命令行参数: `python api_server.py --api-key your_secure_key_here`

示例请求:
```http
GET /api/contacts HTTP/1.1
Host: localhost:8000
X-API-Key: your_api_key_here
```

## API列表

### 1. 健康检查

**请求**:
```http
GET /api/health
```

**响应**:
```json
{
  "code": 200,
  "message": "服务正常",
  "data": {
    "status": "ok"
  },
  "timestamp": 1647356400
}
```

### 2. 获取联系人列表

**请求**:
```http
GET /api/contacts
```

**响应**:
```json
{
  "code": 200,
  "message": "获取联系人列表成功",
  "data": [
    {
      "wxid": "wxid_example1",
      "nickname": "张三",
      "remark": "同事张三",
      "alias": "zhangsan",
      "avatar_url": "http://wx.qlogo.cn/mmhead/example1",
      "contact_type": 1,
      "label": "同事"
    },
    // 更多联系人...
  ],
  "timestamp": 1647356400
}
```

### 3. 获取聊天记录

**请求**:
```http
GET /api/messages?contact_id=wxid_example1&page=1&page_size=20&start_time=1640966400&end_time=1643644800
```

**参数**:
- `contact_id`: (可选) 联系人ID，不提供则获取所有聊天记录
- `page`: (可选) 页码，默认为1
- `page_size`: (可选) 每页数量，默认为20，最大100
- `start_time`: (可选) 开始时间戳
- `end_time`: (可选) 结束时间戳

**响应**:
```json
{
  "code": 200,
  "message": "获取聊天记录成功",
  "data": [
    {
      "msgid": "123456789",
      "talker": "wxid_example1",
      "type": 1,
      "content": "你好，这是一条测试消息",
      "create_time": 1642435200,
      "is_send": 0
    },
    // 更多消息...
  ],
  "timestamp": 1647356400
}
```

### 4. 获取当前微信账号信息

**请求**:
```http
GET /api/account
```

**响应**:
```json
{
  "code": 200,
  "message": "获取账号信息成功",
  "data": {
    "wxid": "wxid_current",
    "nickname": "我的昵称",
    "mobile": "13800138000",
    "avatar_url": "http://wx.qlogo.cn/mmhead/current"
  },
  "timestamp": 1647356400
}
```

## 错误码

| 错误码 | 描述 |
| ------ | ---- |
| 200 | 成功 |
| 400 | 请求参数错误 |
| 401 | 未授权 |
| 404 | 资源未找到 |
| 429 | 请求过于频繁 |
| 500 | 服务器内部错误 |
| 1000 | 数据库操作失败 |
| 1001 | 联系人未找到 |
| 1002 | 聊天记录未找到 |
| 1003 | 账号信息未找到 |

## 其他说明

1. 响应格式统一为：
   ```json
   {
     "code": 200,
     "message": "success",
     "data": {},
     "timestamp": 1647356400
   }
   ```

2. 所有API都有速率限制，默认为每分钟60次请求。

3. 如有任何问题或建议，请联系开发者。 
 