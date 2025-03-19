#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信API服务
提供微信联系人、聊天记录、账号信息等接口
"""

import os
import time
import secrets
import argparse
import logging
from enum import Enum
from typing import List, Dict, Optional, Any, Union, Generic, TypeVar
from functools import wraps
from datetime import datetime

# 添加Qt应用初始化
import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt

import uvicorn
from fastapi import FastAPI, HTTPException, Depends, Security, status, Request, Query
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# API专用日志配置
def setup_api_logger():
    # 创建API专用logger
    api_logger = logging.getLogger('api')
    api_logger.setLevel(logging.DEBUG)
    
    # 格式化器
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # 确保日志目录存在
    log_dir = './log/logs'
    os.makedirs(log_dir, exist_ok=True)
    
    # 日志文件名格式：YYYY-MM-DD-api.log
    filename = time.strftime("%Y-%m-%d", time.localtime(time.time()))
    log_file = os.path.join(log_dir, f'{filename}-api.log')
    
    # 文件处理器
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)
    
    # 添加处理器
    api_logger.addHandler(file_handler)
    api_logger.addHandler(console_handler)
    
    return api_logger

# 创建API日志记录器
api_logger = setup_api_logger()

# 继续使用app.log.logger记录应用日志
# from app.log.logger import logger
from app.DataBase import micro_msg_db, msg_db, misc_db
from app.person import Me

# 初始化Qt应用程序环境，避免QPixmap错误
# 使用QApplication.instance()防止重复创建QApplication
if not QApplication.instance():
    qt_app = QApplication(sys.argv)
    # 设置为后台运行，不显示GUI界面
    qt_app.setQuitOnLastWindowClosed(False)
    api_logger.info("QApplication初始化成功")

# 错误码定义
class ErrorCode:
    SUCCESS = 200  # 成功
    BAD_REQUEST = 400  # 请求参数错误
    UNAUTHORIZED = 401  # 未授权
    NOT_FOUND = 404  # 资源未找到
    TOO_MANY_REQUESTS = 429  # 请求过于频繁
    INTERNAL_ERROR = 500  # 服务器内部错误
    
    # 业务错误码
    DB_ERROR = 1000  # 数据库操作失败
    CONTACT_NOT_FOUND = 1001  # 联系人未找到
    MESSAGE_NOT_FOUND = 1002  # 聊天记录未找到
    ACCOUNT_NOT_FOUND = 1003  # 账号信息未找到
    
    @classmethod
    def message(cls, code):
        """根据错误码获取对应的错误信息"""
        error_messages = {
            cls.SUCCESS.value: "成功",
            cls.BAD_REQUEST.value: "请求参数错误",
            cls.UNAUTHORIZED.value: "未授权",
            cls.NOT_FOUND.value: "资源未找到",
            cls.TOO_MANY_REQUESTS.value: "请求过于频繁",
            cls.INTERNAL_ERROR.value: "服务器内部错误",
            cls.DB_ERROR.value: "数据库操作失败",
            cls.CONTACT_NOT_FOUND.value: "联系人未找到",
            cls.MESSAGE_NOT_FOUND.value: "聊天记录未找到",
            cls.ACCOUNT_NOT_FOUND.value: "账号信息未找到",
        }
        return error_messages.get(code, "未知错误")

# 定义数据模型
T = TypeVar('T')

class ResponseModel(BaseModel, Generic[T]):
    """统一响应模型"""
    code: int = Field(200, description="状态码")
    message: str = Field("success", description="状态信息")
    data: Optional[T] = Field(None, description="响应数据")
    timestamp: int = Field(default_factory=lambda: int(time.time()), description="时间戳")

class ContactModel(BaseModel):
    """联系人模型"""
    wxid: str = Field(..., description="微信ID")
    nickname: str = Field(..., description="昵称")
    remark: Optional[str] = Field(None, description="备注名")
    alias: Optional[str] = Field(None, description="微信号")
    avatar_url: Optional[str] = Field(None, description="头像URL")
    contact_type: Optional[int] = Field(None, description="联系人类型")
    label: Optional[str] = Field(None, description="标签")

class AccountInfoModel(BaseModel):
    """账号信息模型"""
    wxid: str = Field(..., description="微信ID")
    nickname: str = Field(..., description="昵称")
    mobile: Optional[str] = Field(None, description="手机号")
    avatar_url: Optional[str] = Field(None, description="头像URL")

class MessageModel(BaseModel):
    """聊天消息模型"""
    msgid: str = Field(..., description="消息ID")
    talker: Union[str, int] = Field(..., description="发送者ID")
    type: int = Field(..., description="消息类型")
    content: str = Field(..., description="消息内容")
    create_time: int = Field(..., description="创建时间")
    is_send: int = Field(..., description="是否为发送消息")
    
class PaginationParams(BaseModel):
    """分页参数"""
    page: int = Field(1, description="页码", ge=1)
    page_size: int = Field(20, description="每页数量", ge=1, le=100)

# API密钥配置
API_KEY_NAME = "X-API-Key"
# API_KEY = os.environ.get("API_KEY") or "your_api_key_here"  # 建议通过环境变量设置
API_KEY = "J6Onc9Rp-ayy_Q9JGUrziCw7QYP_P8ruorqtIuA6Kyo"

if not API_KEY:
    # 如果环境变量中没有设置，生成一个随机密钥并保存
    API_KEY = secrets.token_urlsafe(32)
    api_logger.warning(f"未设置API密钥环境变量，已生成随机密钥: {API_KEY}")
    with open("api_key.txt", "w") as f:
        f.write(API_KEY)
    api_logger.info("API密钥已保存到 api_key.txt 文件")


# 创建FastAPI应用
app = FastAPI(
    title="微信API服务",
    description="提供微信联系人、聊天记录、账号信息等接口",
    version="1.0.0",
    docs_url=None,  # 禁用默认的Swagger UI路径
)

# 跨域配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API密钥验证
api_key_header = APIKeyHeader(name=API_KEY_NAME)

# 请求计数器，用于简单的限流
request_counter = {}
# 清理间隔（秒）
CLEANUP_INTERVAL = 60
# 请求频率限制（次数/分钟）
RATE_LIMIT = 60

def get_api_key(api_key_header: str = Security(api_key_header)):
    if api_key_header != API_KEY:
        api_logger.warning(f"API密钥验证失败: {api_key_header[:5]}...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的API密钥",
        )
    return api_key_header

# 限流中间件
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    # 获取客户端IP
    client_ip = request.client.host
    current_time = time.time()
    
    # 清理过期的请求计数
    if current_time % CLEANUP_INTERVAL < 1:
        for ip in list(request_counter.keys()):
            if current_time - request_counter[ip]["timestamp"] > 60:
                del request_counter[ip]
    
    # 检查请求计数
    if client_ip in request_counter:
        if current_time - request_counter[client_ip]["timestamp"] <= 60:
            request_counter[client_ip]["count"] += 1
            if request_counter[client_ip]["count"] > RATE_LIMIT:
                api_logger.warning(f"API请求频率超限: {client_ip}, 1分钟内请求{request_counter[client_ip]['count']}次")
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={"detail": "请求过于频繁，请稍后再试"}
                )
        else:
            # 重置计数
            request_counter[client_ip] = {"timestamp": current_time, "count": 1}
    else:
        request_counter[client_ip] = {"timestamp": current_time, "count": 1}
    
    # 处理请求
    response = await call_next(request)
    return response

# 统一异常处理
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    api_logger.error(f"HTTP异常: {exc.detail}, 状态码: {exc.status_code}")
    return JSONResponse(
        status_code=exc.status_code,
        content=ResponseModel(
            code=exc.status_code,
            message=str(exc.detail),
            data=None
        ).dict()
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    api_logger.error(f"系统异常: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ResponseModel(
            code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="服务器内部错误",
            data=None
        ).dict()
    )

# Swagger UI自定义路径
@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=app.title + " - API文档",
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
    )

# 健康检查接口
@app.get("/api/health", tags=["系统"])
async def health_check():
    """
    健康检查接口，用于确认API服务是否正常运行
    """
    api_logger.info("健康检查请求")
    return ResponseModel(
        code=status.HTTP_200_OK,
        message="服务正常",
        data={"status": "ok"}
    )

# 联系人相关API
@app.get("/api/contacts", response_model=ResponseModel[List[ContactModel]], tags=["联系人"])
async def get_contacts(api_key: str = Depends(get_api_key)):
    """
    获取所有联系人列表
    """
    try:
        api_logger.info("获取联系人列表请求")
        contacts_data = micro_msg_db.get_contact()
        
        if not contacts_data:
            api_logger.warning("未找到联系人数据")
            return ResponseModel(
                code=status.HTTP_404_NOT_FOUND,
                message="未找到联系人数据",
                data=[]
            )
        
        contacts = []
        for contact in contacts_data:
            # 解析联系人数据
            # UserName, Alias, Type, Remark, NickName, PYInitial, RemarkPYInitial, smallHeadImgUrl, bigHeadImgUrl, ExtraBuf, labelName
            contacts.append(ContactModel(
                wxid=contact[0],
                nickname=contact[4],
                remark=contact[3],
                alias=contact[1],
                avatar_url=contact[8],  # 使用大头像URL
                contact_type=contact[2],
                label=contact[10]
            ))
        
        api_logger.info(f"成功获取联系人列表，共 {len(contacts)} 条")
        return ResponseModel(
            code=status.HTTP_200_OK,
            message="获取联系人列表成功",
            data=contacts
        )
    except Exception as e:
        api_logger.error(f"获取联系人列表失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取联系人列表失败: {str(e)}"
        )

# 聊天记录相关API
@app.get("/api/messages", response_model=ResponseModel[List[MessageModel]], tags=["聊天记录"])
async def get_messages(
    contact_id: Optional[str] = Query(None, description="联系人ID，为空时获取所有聊天记录"),
    page: int = Query(1, description="页码", ge=1),
    page_size: int = Query(20, description="每页数量", ge=1, le=100),
    start_time: Optional[int] = Query(None, description="开始时间戳"),
    end_time: Optional[int] = Query(None, description="结束时间戳"),
    api_key: str = Depends(get_api_key)
):
    """
    获取聊天记录，可按联系人ID过滤
    """
    try:
        api_logger.info(f"获取聊天记录请求: contact_id={contact_id}, page={page}, page_size={page_size}")
        
        # 构建时间范围参数
        time_range = None
        if start_time and end_time:
            time_range = (start_time, end_time)
        
        # 获取消息数据
        if contact_id:
            # 获取指定联系人的聊天记录
            messages_data = msg_db.get_messages(contact_id, time_range)
        else:
            # 获取所有聊天记录
            messages_data = msg_db.get_messages_all(time_range)
        
        if not messages_data:
            api_logger.warning(f"未找到聊天记录: contact_id={contact_id}")
            return ResponseModel(
                code=status.HTTP_404_NOT_FOUND,
                message="未找到聊天记录",
                data=[]
            )
        
        # 分页处理
        total = len(messages_data)
        start_idx = (page - 1) * page_size
        end_idx = min(start_idx + page_size, total)
        
        # 如果超出范围，返回空数组
        if start_idx >= total:
            api_logger.warning(f"分页超出范围: page={page}, total={total}")
            return ResponseModel(
                code=status.HTTP_200_OK,
                message="获取聊天记录成功",
                data=[]
            )
        
        messages = []
        for msg in messages_data[start_idx:end_idx]:
            try:
                # 解析消息数据
                # localId, talkerId, Type, SubType, IsSender, CreateTime, Status, StrContent, StrTime
                # 调试日志
                api_logger.debug(f"消息数据: {msg}")
                
                # 保证内容是字符串类型
                content = str(msg[7]) if msg[7] is not None else ""
                
                messages.append(MessageModel(
                    msgid=str(msg[0]),
                    talker=msg[1],  # 可以是整数或字符串
                    type=msg[2],
                    content=content,
                    create_time=msg[5],
                    is_send=msg[4]
                ))
            except Exception as item_err:
                # 单条消息处理失败，跳过并记录日志
                api_logger.warning(f"处理单条消息时出错，已跳过: {str(item_err)}, 消息ID: {msg[0] if len(msg) > 0 else '未知'}")
                continue
        
        api_logger.info(f"成功获取聊天记录: contact_id={contact_id}, 共 {total} 条, 当前页 {len(messages)} 条")
        return ResponseModel(
            code=status.HTTP_200_OK,
            message="获取聊天记录成功",
            data=messages
        )
    except Exception as e:
        api_logger.error(f"获取聊天记录失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取聊天记录失败: {str(e)}"
        )

# 微信账号信息API
@app.get("/api/account", response_model=ResponseModel[AccountInfoModel], tags=["账号"])
async def get_account_info(api_key: str = Depends(get_api_key)):
    """
    获取当前微信账号信息
    """
    try:
        api_logger.info("获取微信账号信息请求")
        
        # 从Me单例获取账号信息
        try:
            me = Me()
            api_logger.debug(f"Me对象初始化成功: {me.wxid if hasattr(me, 'wxid') else '无wxid'}")
            
            # 检查必要的属性是否存在
            if not hasattr(me, 'wxid') or not me.wxid:
                api_logger.warning("获取账号信息失败: 无法获取wxid")
                raise ValueError("无法获取wxid")
                
            if not hasattr(me, 'nickName') or not me.nickName:
                api_logger.warning(f"账号 {me.wxid} 无昵称信息")
                me.nickName = "未知用户"
            
            # 构建账号信息响应
            account_info = AccountInfoModel(
                wxid=me.wxid,
                nickname=me.nickName,
                mobile=me.mobile if hasattr(me, 'mobile') else None,
                avatar_url=me.smallHeadImgUrl if hasattr(me, 'smallHeadImgUrl') else None
            )
            
            api_logger.info(f"成功获取账号信息: wxid={account_info.wxid}")
            return ResponseModel(
                code=status.HTTP_200_OK,
                message="获取账号信息成功",
                data=account_info
            )
        except AttributeError as ae:
            api_logger.error(f"获取账号信息属性错误: {str(ae)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"获取账号信息失败: 属性错误 - {str(ae)}"
            )
    except ValueError as ve:
        api_logger.error(f"获取账号信息参数错误: {str(ve)}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"获取账号信息失败: {str(ve)}"
        )
    except Exception as e:
        api_logger.error(f"获取账号信息失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取账号信息失败: {str(e)}"
        )

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="微信API服务")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="服务监听地址")
    parser.add_argument("--port", type=int, default=8000, help="服务监听端口")
    parser.add_argument("--debug", action="store_true", help="是否开启调试模式")
    parser.add_argument("--api-key", type=str, help="设置API密钥，若不设置则使用环境变量或默认值")
    
    args = parser.parse_args()
    
    # # 设置API密钥
    # if args.api_key:
    #     API_KEY = args.api_key
    #     logger.info("使用命令行参数设置的API密钥")
    # elif os.environ.get("API_KEY"):
    #     logger.info("使用环境变量设置的API密钥")
    # else:
    #     logger.warning("使用默认API密钥，建议更换为自定义密钥以提高安全性")
    
    # 初始化数据库连接
    try:
        from app.DataBase import init_db
        init_db()
        api_logger.info("数据库初始化成功")
    except Exception as e:
        api_logger.error(f"数据库初始化失败: {str(e)}")
    
    api_logger.info(f"API服务启动中... 地址: {args.host}, 端口: {args.port}")
    api_logger.info(f"API日志保存路径: ./app/log/logs/{time.strftime('%Y-%m-%d')}-api.log")
    api_logger.info(f"API文档地址: http://{args.host if args.host != '0.0.0.0' else 'localhost'}:{args.port}/docs")
    
    uvicorn.run(app, host=args.host, port=args.port, reload=args.debug, log_level="debug" if args.debug else "info") 