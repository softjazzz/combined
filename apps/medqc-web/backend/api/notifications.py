# 消息通知API端点
# 统一的消息通知管理和WebSocket实时通信

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any, Optional
import asyncio
import json
from datetime import datetime

from ..models.audit_models import (
    QCNotification, QCNotificationBase, MessageType, MessagePriority,
    APIResponse, PaginatedResponse
)
from ..services.notification_service import UnifiedNotificationService
from ..database.database import get_db
from ..auth.dependencies import get_current_user, require_permissions, get_user_from_token

# 假设现有的LLM服务实例
from ..llm_service.llm_client import llm_service

router = APIRouter(prefix="/api/notifications", tags=["消息通知"])

# 初始化统一通知服务
notification_service = UnifiedNotificationService(llm_service)

# WebSocket路由
@router.websocket("/ws/{user_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: str,
    token: str = Query(..., description="认证令牌")
):
    """
    WebSocket实时通知端点
    
    - 支持实时消息推送
    - 自动重连和心跳检测
    - 消息确认和状态同步
    """
    try:
        # 验证用户身份
        user = await get_user_from_token(token)
        if not user or user.id != user_id:
            await websocket.close(code=4001, reason="认证失败")
            return
        
        # 建立连接
        await notification_service.connect_websocket(websocket, user_id)
        
        try:
            # 发送连接确认消息
            await websocket.send_text(json.dumps({
                "type": "connection_established",
                "data": {
                    "user_id": user_id,
                    "timestamp": datetime.utcnow().isoformat(),
                    "message": "WebSocket连接已建立"
                }
            }, ensure_ascii=False))
            
            # 保持连接并处理客户端消息
            while True:
                try:
                    # 接收客户端消息
                    data = await websocket.receive_text()
                    message = json.loads(data)
                    
                    # 处理不同类型的客户端消息
                    await handle_client_message(websocket, user_id, message)
                    
                except WebSocketDisconnect:
                    break
                except json.JSONDecodeError:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "data": {"message": "无效的JSON格式"}
                    }, ensure_ascii=False))
                except Exception as e:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "data": {"message": f"处理消息失败: {str(e)}"}
                    }, ensure_ascii=False))
        
        except WebSocketDisconnect:
            pass
        finally:
            notification_service.disconnect_websocket(websocket)
    
    except Exception as e:
        print(f"WebSocket连接异常: {e}")
        try:
            await websocket.close(code=4000, reason="服务器内部错误")
        except:
            pass

async def handle_client_message(websocket: WebSocket, user_id: str, message: Dict[str, Any]):
    """处理客户端消息"""
    
    message_type = message.get("type")
    
    if message_type == "ping":
        # 心跳检测
        await websocket.send_text(json.dumps({
            "type": "pong",
            "data": {"timestamp": datetime.utcnow().isoformat()}
        }, ensure_ascii=False))
    
    elif message_type == "mark_read":
        # 标记消息已读
        notification_id = message.get("data", {}).get("notification_id")
        if notification_id:
            # 这里需要数据库会话，实际实现中需要传递
            # await notification_service.mark_as_read(notification_id, db)
            await websocket.send_text(json.dumps({
                "type": "read_confirmed",
                "data": {"notification_id": notification_id}
            }, ensure_ascii=False))
    
    elif message_type == "get_unread_count":
        # 获取未读消息数量
        # 实际实现中需要查询数据库
        await websocket.send_text(json.dumps({
            "type": "unread_count",
            "data": {"count": 0}  # 占位符
        }, ensure_ascii=False))

# REST API端点
@router.post("", response_model=APIResponse[QCNotification])
async def send_notification(
    notification_data: QCNotificationBase,
    immediate: bool = Query(True, description="是否立即发送"),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
    _: None = Depends(require_permissions(["notification_send"]))
):
    """
    发送通知消息
    
    - 支持智能内容生成
    - 自动适配用户偏好
    - 多通道分发（WebSocket + 数据库）
    """
    try:
        notification = await notification_service.send_notification(
            notification_data=notification_data,
            db=db,
            immediate=immediate
        )
        
        return APIResponse(
            success=True,
            message="通知发送成功",
            data=notification
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"发送通知失败: {str(e)}"
        )

@router.post("/batch", response_model=APIResponse[List[QCNotification]])
async def batch_send_notifications(
    notifications_data: List[QCNotificationBase],
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
    _: None = Depends(require_permissions(["notification_send"]))
):
    """批量发送通知"""
    try:
        notifications = await notification_service.batch_send_notifications(
            notifications_data=notifications_data,
            db=db
        )
        
        return APIResponse(
            success=True,
            message=f"批量发送 {len(notifications)} 条通知成功",
            data=notifications
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"批量发送通知失败: {str(e)}"
        )

@router.get("", response_model=APIResponse[PaginatedResponse[QCNotification]])
async def get_user_notifications(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    status: Optional[List[str]] = Query(None, description="消息状态"),
    types: Optional[List[MessageType]] = Query(None, description="消息类型"),
    priority: Optional[MessagePriority] = Query(None, description="消息优先级"),
    unread_only: bool = Query(False, description="仅显示未读消息"),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """获取用户通知列表"""
    try:
        # 构建过滤条件
        filters = {}
        
        if status:
            filters["status"] = status
        elif unread_only:
            filters["status"] = ["pending", "delivered"]
        
        if types:
            filters["types"] = types
        
        if priority:
            filters["priority"] = priority
        
        # 查询通知列表
        notifications, total = await notification_service.get_user_notifications(
            user_id=current_user.id,
            filters=filters,
            page=page,
            page_size=page_size,
            db=db
        )
        
        # 构建分页响应
        paginated_response = PaginatedResponse(
            items=notifications,
            total=total,
            page=page,
            page_size=page_size
        )
        
        return APIResponse(
            success=True,
            message="获取通知列表成功",
            data=paginated_response
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"获取通知列表失败: {str(e)}"
        )

@router.put("/{notification_id}/read", response_model=APIResponse[dict])
async def mark_notification_as_read(
    notification_id: str,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """标记通知为已读"""
    try:
        await notification_service.mark_as_read(notification_id, db)
        
        return APIResponse(
            success=True,
            message="消息已标记为已读",
            data={"notification_id": notification_id}
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"标记已读失败: {str(e)}"
        )

@router.put("/{notification_id}/processed", response_model=APIResponse[dict])
async def mark_notification_as_processed(
    notification_id: str,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """标记通知为已处理"""
    try:
        await notification_service.mark_as_processed(notification_id, db)
        
        return APIResponse(
            success=True,
            message="消息已标记为已处理",
            data={"notification_id": notification_id}
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"标记已处理失败: {str(e)}"
        )

@router.post("/batch-read", response_model=APIResponse[dict])
async def batch_mark_as_read(
    notification_ids: List[str],
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """批量标记为已读"""
    try:
        for notification_id in notification_ids:
            await notification_service.mark_as_read(notification_id, db)
        
        return APIResponse(
            success=True,
            message=f"批量标记 {len(notification_ids)} 条消息为已读",
            data={"processed_count": len(notification_ids)}
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"批量标记已读失败: {str(e)}"
        )

@router.get("/stats", response_model=APIResponse[Dict[str, Any]])
async def get_notification_stats(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """获取通知统计信息"""
    try:
        # 获取连接统计
        connection_stats = notification_service.get_connection_stats()
        
        # 获取用户消息统计
        user_stats = await get_user_notification_stats(current_user.id, db)
        
        stats = {
            "connection_stats": connection_stats,
            "user_stats": user_stats,
            "service_status": "running"
        }
        
        return APIResponse(
            success=True,
            message="获取统计信息成功",
            data=stats
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"获取统计信息失败: {str(e)}"
        )

@router.post("/test", response_model=APIResponse[QCNotification])
async def send_test_notification(
    recipient_id: str,
    message_type: MessageType = MessageType.SYSTEM_ANNOUNCEMENT,
    priority: MessagePriority = MessagePriority.NORMAL,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
    _: None = Depends(require_permissions(["notification_test"]))
):
    """发送测试通知"""
    try:
        test_notification = QCNotificationBase(
            type=message_type,
            priority=priority,
            recipient_id=recipient_id,
            recipient_type="reviewer",
            title="测试通知",
            content="这是一条测试通知消息，用于验证通知系统功能。",
            summary="测试通知",
            related_data={
                "test": True,
                "sender": current_user.id,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        notification = await notification_service.send_notification(
            notification_data=test_notification,
            db=db,
            immediate=True
        )
        
        return APIResponse(
            success=True,
            message="测试通知发送成功",
            data=notification
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"发送测试通知失败: {str(e)}"
        )

# 辅助函数
async def get_user_notification_stats(user_id: str, db: AsyncSession) -> Dict[str, Any]:
    """获取用户通知统计"""
    # 实现用户通知统计查询
    # 这里是简化实现
    return {
        "total_notifications": 0,
        "unread_count": 0,
        "today_count": 0,
        "by_type": {},
        "by_priority": {}
    }

# 服务启动和关闭事件
@router.on_event("startup")
async def startup_notification_service():
    """启动通知服务"""
    await notification_service.start_service()

@router.on_event("shutdown")
async def shutdown_notification_service():
    """关闭通知服务"""
    await notification_service.stop_service()

# 健康检查端点
@router.get("/health", response_model=APIResponse[Dict[str, Any]])
async def notification_service_health_check():
    """通知服务健康检查"""
    try:
        connection_stats = notification_service.get_connection_stats()
        
        return APIResponse(
            success=True,
            message="通知服务运行正常",
            data={
                "service": "notification_service",
                "status": "healthy",
                "connection_stats": connection_stats,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
    except Exception as e:
        return APIResponse(
            success=False,
            message="通知服务异常",
            data={
                "service": "notification_service",
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )
