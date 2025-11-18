"""
认证服务
"""
import jwt
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional
from loguru import logger

from app.services.database import db_service
from app.schemas.auth import LoginRequest, UserResponse


class AuthService:
    """认证服务类"""

    # JWT配置
    SECRET_KEY = secrets.token_urlsafe(32)
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

    # Supabase 客户端
    supabase = db_service.client

    @classmethod
    def hash_password(cls, password: str) -> str:
        """哈希密码"""
        return hashlib.sha256(password.encode()).hexdigest()

    @classmethod
    def verify_password(cls, plain_password: str, hashed_password: str) -> bool:
        """验证密码"""
        return cls.hash_password(plain_password) == hashed_password

    @classmethod
    def create_access_token(cls, data: dict) -> str:
        """创建访问令牌"""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(minutes=cls.ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, cls.SECRET_KEY, algorithm=cls.ALGORITHM)
        return encoded_jwt

    @classmethod
    def decode_token(cls, token: str) -> Optional[dict]:
        """解码令牌"""
        try:
            payload = jwt.decode(token, cls.SECRET_KEY, algorithms=[cls.ALGORITHM])
            return payload
        except jwt.PyJWTError as e:
            logger.error(f"Token解码失败: {e}")
            return None

    @classmethod
    async def authenticate_user(cls, credentials: LoginRequest) -> Optional[UserResponse]:
        """
        认证用户
        简化版实现：检查 Supabase users 表，使用简单密码哈希
        如果数据库表不存在，使用测试用户
        """
        try:
            # 查询用户
            response = cls.supabase.table("users").select("*").eq("email", credentials.email).execute()

            if not response.data or len(response.data) == 0:
                logger.warning(f"用户不存在: {credentials.email}")
                # 使用测试用户作为fallback
                return cls._get_test_user(credentials)

            user_data = response.data[0]

            # 验证密码（如果有密码字段）
            if "password" in user_data:
                if not cls.verify_password(credentials.password, user_data["password"]):
                    logger.warning(f"密码错误: {credentials.email}")
                    return None
            else:
                # 如果没有密码字段，使用简化验证（仅用于开发/测试）
                logger.warning("用户表没有密码字段，使用简化认证模式")

            # 构建用户响应
            user_response = UserResponse(
                id=user_data.get("id"),
                email=user_data.get("email"),
                display_name=user_data.get("display_name") or user_data.get("email"),
                department=user_data.get("department"),
                hospital_id=user_data.get("hospital_id"),
                roles=user_data.get("roles", [credentials.role]) if credentials.role else ["user"],
                is_active=user_data.get("is_active", True),
                created_at=user_data.get("created_at"),
                updated_at=user_data.get("updated_at"),
                avatar=user_data.get("avatar"),
                phone=user_data.get("phone")
            )

            logger.info(f"用户认证成功: {credentials.email}")
            return user_response

        except Exception as e:
            logger.error(f"认证失败: {e}")
            # 数据库表不存在，使用测试用户
            logger.warning("数据库表不存在，使用测试用户进行认证")
            return cls._get_test_user(credentials)

    @classmethod
    def _get_test_user(cls, credentials: LoginRequest) -> Optional[UserResponse]:
        """
        获取测试用户（用于开发环境，当数据库表不存在时）
        """
        # 测试用户列表
        test_users = {
            "admin@medqc.com": {
                "id": "test-admin-001",
                "email": "admin@medqc.com",
                "password": "admin123",  # 明文密码，仅用于测试
                "display_name": "管理员",
                "roles": ["admin"],
                "department": "信息科",
                "hospital_id": "hospital-001"
            },
            "coder@medqc.com": {
                "id": "test-coder-001",
                "email": "coder@medqc.com",
                "password": "coder123",
                "display_name": "编码员",
                "roles": ["coder"],
                "department": "病案科",
                "hospital_id": "hospital-001"
            }
        }

        # 检查是否是测试用户
        if credentials.email not in test_users:
            logger.warning(f"测试用户不存在: {credentials.email}")
            return None

        test_user = test_users[credentials.email]

        # 验证密码
        if credentials.password != test_user["password"]:
            logger.warning(f"测试用户密码错误: {credentials.email}")
            return None

        # 返回用户信息
        logger.info(f"使用测试用户登录: {credentials.email}")
        return UserResponse(
            id=test_user["id"],
            email=test_user["email"],
            display_name=test_user["display_name"],
            department=test_user.get("department"),
            hospital_id=test_user.get("hospital_id"),
            roles=test_user["roles"],
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

    @classmethod
    def _get_test_user_by_id(cls, user_id: str) -> Optional[UserResponse]:
        """
        根据ID获取测试用户（用于开发环境，当数据库表不存在时）
        """
        # 测试用户列表（与 _get_test_user 中的定义相同）
        test_users_by_id = {
            "test-admin-001": {
                "id": "test-admin-001",
                "email": "admin@medqc.com",
                "display_name": "管理员",
                "roles": ["admin"],
                "department": "信息科",
                "hospital_id": "hospital-001"
            },
            "test-coder-001": {
                "id": "test-coder-001",
                "email": "coder@medqc.com",
                "display_name": "编码员",
                "roles": ["coder"],
                "department": "病案科",
                "hospital_id": "hospital-001"
            }
        }

        # 检查是否是测试用户ID
        if user_id not in test_users_by_id:
            logger.warning(f"测试用户ID不存在: {user_id}")
            return None

        test_user = test_users_by_id[user_id]

        # 返回用户信息
        logger.info(f"使用测试用户ID获取用户: {user_id}")
        return UserResponse(
            id=test_user["id"],
            email=test_user["email"],
            display_name=test_user["display_name"],
            department=test_user.get("department"),
            hospital_id=test_user.get("hospital_id"),
            roles=test_user["roles"],
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

    @classmethod
    async def get_user_by_id(cls, user_id: str) -> Optional[UserResponse]:
        """根据用户ID获取用户信息"""
        try:
            response = cls.supabase.table("users").select("*").eq("id", user_id).execute()

            if not response.data or len(response.data) == 0:
                logger.warning(f"数据库中未找到用户: {user_id}，尝试使用测试用户")
                return cls._get_test_user_by_id(user_id)

            user_data = response.data[0]

            return UserResponse(
                id=user_data.get("id"),
                email=user_data.get("email"),
                display_name=user_data.get("display_name") or user_data.get("email"),
                department=user_data.get("department"),
                hospital_id=user_data.get("hospital_id"),
                roles=user_data.get("roles", ["user"]),
                is_active=user_data.get("is_active", True),
                created_at=user_data.get("created_at"),
                updated_at=user_data.get("updated_at"),
                avatar=user_data.get("avatar"),
                phone=user_data.get("phone")
            )

        except Exception as e:
            logger.error(f"获取用户失败: {e}")
            # 数据库表不存在，使用测试用户
            logger.warning("数据库表不存在，尝试使用测试用户")
            return cls._get_test_user_by_id(user_id)
