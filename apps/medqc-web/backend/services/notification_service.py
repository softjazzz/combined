# 统一消息通知服务
# 集成WebSocket和Supabase实时功能的消息通知系统

import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Set
from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_
import logging

from ..models.audit_models import (
    QCNotification, MessageType, MessagePriority, MessageAction,
    QCNotificationBase
)
from ..database.models import QCNotificationDB, UserNotificationPreferencesDB

# 假设现有的LLM服务接口
class LLMServiceInterface:
    async def generate_response(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """生成LLM响应"""
        pass

logger = logging.getLogger(__name__)

class ConnectionManager:
    """WebSocket连接管理器"""
    
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self.user_connections: Dict[str, str] = {}  # websocket_id -> user_id
    
    async def connect(self, websocket: WebSocket, user_id: str):
        """建立WebSocket连接"""
        await websocket.accept()
        
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        
        self.active_connections[user_id].add(websocket)
        self.user_connections[id(websocket)] = user_id
        
        logger.info(f"用户 {user_id} 建立WebSocket连接")
    
    def disconnect(self, websocket: WebSocket):
        """断开WebSocket连接"""
        websocket_id = id(websocket)
        
        if websocket_id in self.user_connections:
            user_id = self.user_connections[websocket_id]
            
            if user_id in self.active_connections:
                self.active_connections[user_id].discard(websocket)
                
                if not self.active_connections[user_id]:
                    del self.active_connections[user_id]
            
            del self.user_connections[websocket_id]
            logger.info(f"用户 {user_id} 断开WebSocket连接")
    
    async def send_personal_message(self, message: Dict[str, Any], user_id: str):
        """发送个人消息"""
        if user_id in self.active_connections:
            disconnected_connections = set()
            
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_text(json.dumps(message, ensure_ascii=False))
                except Exception as e:
                    logger.warning(f"发送消息失败: {e}")
                    disconnected_connections.add(connection)
            
            # 清理断开的连接
            for connection in disconnected_connections:
                self.active_connections[user_id].discard(connection)
    
    async def broadcast_message(self, message: Dict[str, Any], user_ids: List[str] = None):
        """广播消息"""
        target_users = user_ids or list(self.active_connections.keys())
        
        for user_id in target_users:
            await self.send_personal_message(message, user_id)
    
    def get_connected_users(self) -> List[str]:
        """获取在线用户列表"""
        return list(self.active_connections.keys())

class IntelligentMessageGenerator:
    """智能消息生成器"""
    
    def __init__(self, llm_service: LLMServiceInterface):
        self.llm_service = llm_service
        self.message_templates = self._load_message_templates()
    
    async def generate_smart_notification(
        self,
        message_type: MessageType,
        recipient_type: str,
        context_data: Dict[str, Any],
        user_preferences: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """生成智能通知内容"""
        
        try:
            # 构建LLM提示词
            prompt = self._build_notification_prompt(
                message_type, recipient_type, context_data, user_preferences
            )
            
            # 调用LLM服务生成内容
            llm_response = await self.llm_service.generate_response(
                prompt=prompt,
                temperature=0.7,
                max_tokens=800
            )
            
            # 解析生成的内容
            generated_content = self._parse_generated_content(llm_response)
            
            return {
                "title": generated_content.get("title", self._get_default_title(message_type)),
                "content": generated_content.get("content", ""),
                "summary": generated_content.get("summary", ""),
                "priority": generated_content.get("priority", MessagePriority.NORMAL),
                "actions": generated_content.get("actions", [])
            }
            
        except Exception as e:
            logger.warning(f"智能消息生成失败: {e}")
            return self._get_fallback_notification(message_type, context_data)
    
    def _build_notification_prompt(
        self,
        message_type: MessageType,
        recipient_type: str,
        context_data: Dict[str, Any],
        user_preferences: Optional[Dict[str, Any]]
    ) -> str:
        """构建通知生成提示词"""
        
        base_prompt = f"""
请生成一条专业的医疗质控消息通知：

消息类型：{message_type}
接收者类型：{recipient_type}
上下文信息：{json.dumps(context_data, ensure_ascii=False, indent=2)}
"""
        
        if user_preferences:
            base_prompt += f"\n用户偏好：{json.dumps(user_preferences, ensure_ascii=False, indent=2)}"
        
        type_specific_prompts = {
            MessageType.RECTIFICATION_REQUIRED: """
这是一条整改要求通知，需要包含：
1. 明确的问题描述
2. 具体的整改要求
3. 整改建议和参考标准
4. 预期完成时间
5. 联系方式

请生成专业、清晰、有建设性的通知内容。
""",
            MessageType.AUDIT_RESULT: """
这是一条审核结果通知，需要包含：
1. 审核结论概述
2. 主要发现和问题
3. 评分情况
4. 后续处理建议

请保持客观、专业的语调。
""",
            MessageType.TASK_ASSIGNED: """
这是一条任务分配通知，需要包含：
1. 任务基本信息
2. 工作要求和标准
3. 完成时间要求
4. 注意事项

请使用鼓励性和指导性的语言。
"""
        }
        
        specific_prompt = type_specific_prompts.get(message_type, "请生成相应的通知内容。")
        
        return f"""{base_prompt}\n{specific_prompt}\n
请严格按照以下JSON格式返回：
{{
  "title": "消息标题",
  "content": "详细内容",
  "summary": "内容摘要（50字以内）",
  "priority": "消息优先级(low/normal/high/urgent)",
  "actions": [
    {{
      "id": "action_id",
      "label": "操作标签",
      "type": "primary|secondary|danger",
      "action": "navigate|api_call|modal",
      "config": {{
        "url": "跳转链接",
        "params": {{}}
      }}
    }}
  ]
}}
"""
    
    def _parse_generated_content(self, llm_response: Dict[str, Any]) -> Dict[str, Any]:
        """解析LLM生成的内容"""
        try:
            content = llm_response.get("content", "")
            
            # 尝试解析JSON响应
            json_match = content.find('{')
            if json_match != -1:
                json_end = content.rfind('}') + 1
                json_content = content[json_match:json_end]
                return json.loads(json_content)
            
        except Exception as e:
            logger.warning(f"解析LLM响应失败: {e}")
        
        return {}
    
    def _get_default_title(self, message_type: MessageType) -> str:
        """获取默认标题"""
        title_map = {
            MessageType.RECTIFICATION_REQUIRED: "病历整改通知",
            MessageType.AUDIT_RESULT: "审核结果通知",
            MessageType.TASK_ASSIGNED: "审核任务分配",
            MessageType.DEADLINE_REMINDER: "截止时间提醒",
            MessageType.SYSTEM_ANNOUNCEMENT: "系统公告"
        }
        return title_map.get(message_type, "系统通知")
    
    def _get_fallback_notification(
        self, 
        message_type: MessageType, 
        context_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """获取回退通知内容"""
        return {
            "title": self._get_default_title(message_type),
            "content": f"您有新的{message_type}消息，请及时查看。",
            "summary": f"{message_type}消息",
            "priority": MessagePriority.NORMAL,
            "actions": []
        }
    
    def _load_message_templates(self) -> Dict[str, Any]:
        """加载消息模板"""
        # 实际实现中可以从配置文件或数据库加载
        return {}

class UnifiedNotificationService:
    """统一消息通知服务"""
    
    def __init__(self, llm_service: LLMServiceInterface):
        self.connection_manager = ConnectionManager()
        self.message_generator = IntelligentMessageGenerator(llm_service)
        self.message_queue = asyncio.Queue()
        self.processing_task = None
    
    async def start_service(self):
        """启动通知服务"""
        if not self.processing_task:
            self.processing_task = asyncio.create_task(self._process_message_queue())
            logger.info("消息通知服务已启动")
    
    async def stop_service(self):
        """停止通知服务"""
        if self.processing_task:
            self.processing_task.cancel()
            try:
                await self.processing_task
            except asyncio.CancelledError:
                pass
            self.processing_task = None
            logger.info("消息通知服务已停止")
    
    async def connect_websocket(self, websocket: WebSocket, user_id: str):
        """建立WebSocket连接"""
        await self.connection_manager.connect(websocket, user_id)
    
    def disconnect_websocket(self, websocket: WebSocket):
        """断开WebSocket连接"""
        self.connection_manager.disconnect(websocket)
    
    async def send_notification(
        self,
        notification_data: QCNotificationBase,
        db: AsyncSession,
        immediate: bool = True
    ) -> QCNotification:
        """发送通知"""
        
        try:
            # 1. 获取用户通知偏好
            user_preferences = await self._get_user_preferences(
                notification_data.recipient_id, db
            )
            
            # 2. 生成智能通知内容
            if not notification_data.title or not notification_data.content:
                generated_content = await self.message_generator.generate_smart_notification(
                    message_type=notification_data.type,
                    recipient_type=notification_data.recipient_type,
                    context_data=notification_data.related_data,
                    user_preferences=user_preferences
                )
                
                # 合并生成的内容
                if not notification_data.title:
                    notification_data.title = generated_content["title"]
                if not notification_data.content:
                    notification_data.content = generated_content["content"]
                if not notification_data.summary:
                    notification_data.summary = generated_content["summary"]
                if not notification_data.actions:
                    notification_data.actions = generated_content["actions"]
            
            # 3. 保存到数据库
            notification_record = QCNotificationDB(
                id=str(uuid.uuid4()),
                **notification_data.dict(),
                status="pending",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            db.add(notification_record)
            await db.flush()
            
            # 4. 转换为响应模型
            notification = QCNotification.from_orm(notification_record)
            
            # 5. 发送通知
            if immediate:
                await self._deliver_notification(notification)
            else:
                await self.message_queue.put(notification)
            
            await db.commit()
            
            logger.info(f"通知已发送: {notification.title} -> {notification.recipient_id}")
            return notification
            
        except Exception as e:
            await db.rollback()
            logger.error(f"发送通知失败: {e}")
            raise e
    
    async def batch_send_notifications(
        self,
        notifications_data: List[QCNotificationBase],
        db: AsyncSession
    ) -> List[QCNotification]:
        """批量发送通知"""
        
        results = []
        
        try:
            # 批量保存到数据库
            notification_records = []
            for notification_data in notifications_data:
                record = QCNotificationDB(
                    id=str(uuid.uuid4()),
                    **notification_data.dict(),
                    status="pending",
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                notification_records.append(record)
            
            db.add_all(notification_records)
            await db.flush()
            
            # 转换为响应模型并加入队列
            for record in notification_records:
                notification = QCNotification.from_orm(record)
                results.append(notification)
                await self.message_queue.put(notification)
            
            await db.commit()
            
            logger.info(f"批量发送 {len(results)} 条通知")
            return results
            
        except Exception as e:
            await db.rollback()
            logger.error(f"批量发送通知失败: {e}")
            raise e
    
    async def mark_as_read(self, notification_id: str, db: AsyncSession):
        """标记消息为已读"""
        await db.execute(
            update(QCNotificationDB)
            .where(QCNotificationDB.id == notification_id)
            .values(
                status="read",
                read_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
        )
        await db.commit()
    
    async def mark_as_processed(self, notification_id: str, db: AsyncSession):
        """标记消息为已处理"""
        await db.execute(
            update(QCNotificationDB)
            .where(QCNotificationDB.id == notification_id)
            .values(
                status="processed",
                processed_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
        )
        await db.commit()
    
    async def get_user_notifications(
        self,
        user_id: str,
        filters: Dict[str, Any],
        page: int = 1,
        page_size: int = 20,
        db: AsyncSession
    ) -> tuple[List[QCNotification], int]:
        """获取用户通知列表"""
        
        query = select(QCNotificationDB).where(
            QCNotificationDB.recipient_id == user_id
        )
        
        # 应用过滤条件
        if filters.get("status"):
            query = query.where(QCNotificationDB.status.in_(filters["status"]))
        
        if filters.get("types"):
            query = query.where(QCNotificationDB.type.in_(filters["types"]))
        
        if filters.get("priority"):
            query = query.where(QCNotificationDB.priority == filters["priority"])
        
        # 计算总数
        count_result = await db.execute(
            select(func.count(QCNotificationDB.id)).select_from(query.subquery())
        )
        total = count_result.scalar() or 0
        
        # 分页查询
        offset = (page - 1) * page_size
        result = await db.execute(
            query.order_by(QCNotificationDB.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        
        notifications = [QCNotification.from_orm(record) for record in result.scalars().all()]
        
        return notifications, total
    
    async def _deliver_notification(self, notification: QCNotification):
        """投递通知"""
        
        # 1. WebSocket实时推送
        await self._send_websocket_notification(notification)
        
        # 2. 更新投递状态
        # 这里可以添加数据库状态更新逻辑
        
        logger.debug(f"通知已投递: {notification.id}")
    
    async def _send_websocket_notification(self, notification: QCNotification):
        """通过WebSocket发送通知"""
        
        message = {
            "type": "notification",
            "data": notification.dict()
        }
        
        await self.connection_manager.send_personal_message(
            message, notification.recipient_id
        )
    
    async def _process_message_queue(self):
        """处理消息队列"""
        
        while True:
            try:
                # 从队列获取消息
                notification = await self.message_queue.get()
                
                # 投递消息
                await self._deliver_notification(notification)
                
                # 标记任务完成
                self.message_queue.task_done()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"处理消息队列失败: {e}")
                await asyncio.sleep(1)  # 避免快速重试
    
    async def _get_user_preferences(
        self, 
        user_id: str, 
        db: AsyncSession
    ) -> Optional[Dict[str, Any]]:
        """获取用户通知偏好"""
        
        result = await db.execute(
            select(UserNotificationPreferencesDB)
            .where(UserNotificationPreferencesDB.user_id == user_id)
        )
        
        preferences = result.scalar_one_or_none()
        
        if preferences:
            return {
                "preferred_channel": preferences.preferred_channel,
                "message_type_preferences": preferences.message_type_preferences,
                "quiet_hours": {
                    "start": preferences.quiet_hours_start,
                    "end": preferences.quiet_hours_end
                }
            }
        
        return None
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """获取连接统计信息"""
        return {
            "connected_users": len(self.connection_manager.active_connections),
            "total_connections": sum(
                len(connections) 
                for connections in self.connection_manager.active_connections.values()
            ),
            "queue_size": self.message_queue.qsize()
        }
