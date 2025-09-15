"""
质控引擎稳健性模块
提供重试、熔断、降级等机制
"""

import time
import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
import threading
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

T = TypeVar('T')

class CircuitState(str, Enum):
    """熔断器状态"""
    CLOSED = "closed"      # 正常状态
    OPEN = "open"          # 熔断状态
    HALF_OPEN = "half_open"  # 半开状态


@dataclass
class RetryConfig:
    """重试配置"""
    max_attempts: int = 3
    base_delay: float = 1.0  # 基础延迟（秒）
    max_delay: float = 60.0  # 最大延迟（秒）
    exponential_base: float = 2.0  # 指数退避基数
    jitter: bool = True  # 是否添加随机抖动


@dataclass
class CircuitBreakerConfig:
    """熔断器配置"""
    failure_threshold: int = 5  # 失败阈值
    recovery_timeout: float = 60.0  # 恢复超时（秒）
    success_threshold: int = 3  # 半开状态成功阈值
    timeout: float = 30.0  # 请求超时（秒）


@dataclass
class CircuitBreakerStats:
    """熔断器统计"""
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    total_requests: int = 0
    total_failures: int = 0


class CircuitBreaker:
    """熔断器实现"""
    
    def __init__(self, name: str, config: CircuitBreakerConfig):
        self.name = name
        self.config = config
        self.stats = CircuitBreakerStats()
        self._lock = threading.Lock()
    
    def __call__(self, func: Callable[..., T]) -> Callable[..., T]:
        """装饰器用法"""
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            return self.call(func, *args, **kwargs)
        return wrapper
    
    def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """执行函数调用"""
        with self._lock:
            self.stats.total_requests += 1
            
            # 检查熔断器状态
            if self.stats.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self.stats.state = CircuitState.HALF_OPEN
                    self.stats.success_count = 0
                    logger.info(f"Circuit breaker {self.name} entering HALF_OPEN state")
                else:
                    raise CircuitBreakerOpenError(f"Circuit breaker {self.name} is OPEN")
        
        try:
            # 执行函数
            start_time = time.time()
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            
            # 检查超时
            if execution_time > self.config.timeout:
                raise TimeoutError(f"Function execution exceeded {self.config.timeout}s")
            
            # 记录成功
            self._record_success()
            return result
            
        except Exception as e:
            # 记录失败
            self._record_failure()
            raise
    
    def _should_attempt_reset(self) -> bool:
        """检查是否应该尝试重置"""
        if self.stats.last_failure_time is None:
            return True
        
        time_since_failure = datetime.now() - self.stats.last_failure_time
        return time_since_failure.total_seconds() >= self.config.recovery_timeout
    
    def _record_success(self):
        """记录成功"""
        with self._lock:
            self.stats.last_success_time = datetime.now()
            
            if self.stats.state == CircuitState.HALF_OPEN:
                self.stats.success_count += 1
                if self.stats.success_count >= self.config.success_threshold:
                    self.stats.state = CircuitState.CLOSED
                    self.stats.failure_count = 0
                    logger.info(f"Circuit breaker {self.name} reset to CLOSED state")
            elif self.stats.state == CircuitState.CLOSED:
                self.stats.failure_count = 0
    
    def _record_failure(self):
        """记录失败"""
        with self._lock:
            self.stats.failure_count += 1
            self.stats.total_failures += 1
            self.stats.last_failure_time = datetime.now()
            
            if (self.stats.state == CircuitState.CLOSED and 
                self.stats.failure_count >= self.config.failure_threshold):
                self.stats.state = CircuitState.OPEN
                logger.warning(f"Circuit breaker {self.name} opened due to {self.stats.failure_count} failures")
            elif self.stats.state == CircuitState.HALF_OPEN:
                self.stats.state = CircuitState.OPEN
                logger.warning(f"Circuit breaker {self.name} reopened due to failure in HALF_OPEN state")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            return {
                'name': self.name,
                'state': self.stats.state.value,
                'failure_count': self.stats.failure_count,
                'success_count': self.stats.success_count,
                'total_requests': self.stats.total_requests,
                'total_failures': self.stats.total_failures,
                'failure_rate': self.stats.total_failures / max(self.stats.total_requests, 1),
                'last_failure_time': self.stats.last_failure_time.isoformat() if self.stats.last_failure_time else None,
                'last_success_time': self.stats.last_success_time.isoformat() if self.stats.last_success_time else None
            }


class CircuitBreakerOpenError(Exception):
    """熔断器开启异常"""
    pass


def retry_with_backoff(config: RetryConfig):
    """重试装饰器"""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None
            
            for attempt in range(config.max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    if attempt == config.max_attempts - 1:
                        # 最后一次尝试，抛出异常
                        logger.error(f"Function {func.__name__} failed after {config.max_attempts} attempts: {e}")
                        raise
                    
                    # 计算延迟时间
                    delay = min(
                        config.base_delay * (config.exponential_base ** attempt),
                        config.max_delay
                    )
                    
                    # 添加随机抖动
                    if config.jitter:
                        import random
                        delay *= (0.5 + random.random() * 0.5)
                    
                    logger.warning(f"Function {func.__name__} failed (attempt {attempt + 1}/{config.max_attempts}), retrying in {delay:.2f}s: {e}")
                    time.sleep(delay)
            
            # 理论上不会到达这里
            raise last_exception
        
        return wrapper
    return decorator


class FallbackHandler:
    """降级处理器"""
    
    def __init__(self, name: str):
        self.name = name
        self.fallback_functions: Dict[str, Callable] = {}
    
    def register_fallback(self, operation: str, fallback_func: Callable):
        """注册降级函数"""
        self.fallback_functions[operation] = fallback_func
        logger.info(f"Registered fallback for operation '{operation}' in handler '{self.name}'")
    
    def execute_with_fallback(self, operation: str, primary_func: Callable, *args, **kwargs):
        """执行主函数，失败时使用降级函数"""
        try:
            return primary_func(*args, **kwargs)
        except Exception as e:
            logger.warning(f"Primary function failed for operation '{operation}': {e}")
            
            if operation in self.fallback_functions:
                try:
                    logger.info(f"Executing fallback for operation '{operation}'")
                    return self.fallback_functions[operation](*args, **kwargs)
                except Exception as fallback_error:
                    logger.error(f"Fallback function also failed for operation '{operation}': {fallback_error}")
                    raise fallback_error
            else:
                logger.error(f"No fallback registered for operation '{operation}'")
                raise e


# 全局熔断器管理器
class CircuitBreakerManager:
    """熔断器管理器"""
    
    def __init__(self):
        self.breakers: Dict[str, CircuitBreaker] = {}
        self._lock = threading.Lock()
    
    def get_breaker(self, name: str, config: Optional[CircuitBreakerConfig] = None) -> CircuitBreaker:
        """获取或创建熔断器"""
        with self._lock:
            if name not in self.breakers:
                if config is None:
                    config = CircuitBreakerConfig()
                self.breakers[name] = CircuitBreaker(name, config)
            return self.breakers[name]
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """获取所有熔断器统计"""
        with self._lock:
            return {name: breaker.get_stats() for name, breaker in self.breakers.items()}


# 全局实例
circuit_breaker_manager = CircuitBreakerManager()
fallback_handler = FallbackHandler("global")


# 便捷函数
def with_circuit_breaker(name: str, config: Optional[CircuitBreakerConfig] = None):
    """熔断器装饰器"""
    breaker = circuit_breaker_manager.get_breaker(name, config)
    return breaker


def with_retry(max_attempts: int = 3, base_delay: float = 1.0):
    """重试装饰器（简化版）"""
    config = RetryConfig(max_attempts=max_attempts, base_delay=base_delay)
    return retry_with_backoff(config)


# 预定义的配置
DEFAULT_RETRY_CONFIG = RetryConfig(max_attempts=3, base_delay=1.0)
AGGRESSIVE_RETRY_CONFIG = RetryConfig(max_attempts=5, base_delay=0.5, max_delay=10.0)
CONSERVATIVE_CIRCUIT_CONFIG = CircuitBreakerConfig(failure_threshold=10, recovery_timeout=120.0)
AGGRESSIVE_CIRCUIT_CONFIG = CircuitBreakerConfig(failure_threshold=3, recovery_timeout=30.0)
