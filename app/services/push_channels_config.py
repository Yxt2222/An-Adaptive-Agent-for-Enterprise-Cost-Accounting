# app/services/push_channels_config.py
from pathlib import Path
import yaml
from typing import Dict, Any, List, Optional

class PushChannelsConfig:
    """
    加载推送渠道YAML配置，管理各渠道开关、目标、消息模板及fallback关键词映射。
    """
    
    _config_path = Path("config/push_channels_config.yaml")
    _config_cache: Optional[Dict[str, Any]] = None
    
    @classmethod
    def load_config(cls) -> Dict[str, Any]:
        """
        加载配置文件
        使用单例模式缓存配置，避免重复读取文件
        如果配置文件不存在，抛出 FileNotFoundError
        如果配置文件内容无效，抛出 ValueError
        """
        if cls._config_cache is not None:
            return cls._config_cache
        
        if not cls._config_path.exists():
            raise FileNotFoundError(
                f"Push channels config file not found: {cls._config_path}"
            )
        
        with open(cls._config_path, 'r', encoding='utf-8') as f:
            cls._config_cache = yaml.safe_load(f)
            if cls._config_cache is None:
                raise ValueError(f"Push channels config file is empty: {cls._config_path}")
        
        return cls._config_cache
    
    @classmethod
    def get_channel_config(cls, channel: str) -> Optional[Dict[str, Any]]:
        """
        获取指定渠道的配置
        """
        config = cls.load_config()
        channels = config.get("push_channels", {})
        return channels.get(channel)
    
    @classmethod
    def is_channel_enabled(cls, channel: str) -> bool:
        """
        检查渠道是否启用
        """
        channel_config = cls.get_channel_config(channel)
        if not channel_config:
            return False
        return channel_config.get("enabled", False)
    
    @classmethod
    def get_channel_targets(cls, channel: str) -> List[Dict[str, Any]]:
        """
        获取渠道的默认目标
        """
        channel_config = cls.get_channel_config(channel)
        if not channel_config:
            return []
        return channel_config.get("default_targets", [])
    
    @classmethod
    def get_message_template(cls, channel: str) -> Optional[str]:
        """
        获取渠道的消息模板
        """
        channel_config = cls.get_channel_config(channel)
        if not channel_config:
            return None
        return channel_config.get("message_template")
    
    @classmethod
    def get_fallback_config(cls) -> Dict[str, Any]:
        """
        获取 fallback 配置
        """
        config = cls.load_config()
        return config.get("fallback", {})
    
    @classmethod
    def get_keyword_mapping(cls) -> List[Dict[str, Any]]:
        """
        获取关键词映射
        """
        fallback_config = cls.get_fallback_config()
        return fallback_config.get("keyword_mapping", [])
    
    @classmethod
    def get_default_channel(cls) -> str:
        """
        获取默认降级通道
        """
        fallback_config = cls.get_fallback_config()
        return fallback_config.get("default_channel", "none")
