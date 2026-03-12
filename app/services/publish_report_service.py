# app/services/publish_report_service.py
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
from pathlib import Path
import json
import requests
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

from app.services.push_channels_config import PushChannelsConfig
from openai import OpenAI

class ExtractedPublishInfo(BaseModel):
    channel : Optional[str] = None
    targets: Optional[List[str]] = None
    
class PublishReportService:
    """
    负责成本报告发布的所有逻辑，整合意图解析与发送逻辑，根据配置将报告推送到指定渠道，返回发送结果
    关键词：
    - 意图解析（LLM + 多层级 fallback）
    - 推送渠道管理
    - 实际发送执行
    """

    def __init__(self):
        # 不需要 db，只处理推送逻辑
        pass

    # ===============================
    # 公共接口
    # ===============================

    def parse_publish_intent(
        self,
        user_query: str,
    ) -> Dict[str, Any]:
        """
        解析用户的发布意图
        
        多层级 fallback:
        Level 1: LLM 解析成功 → 返回解析结果
        Level 2: 关键词匹配 fallback → 返回匹配结果
        Level 3: 默认降级 → 返回 "none" (网页端)
        
        Returns:
            {
                "channel": "wechat" | "dingtalk" | "email" | "none",
                "targets": List[str],  # 目标 ID 或邮箱
                "fallback_used": bool,  # 是否使用了 fallback
                "llm_parsed": bool,  # LLM 是否成功解析
                "original_query": str,
            }
        """
        result = {
            "channel": "none",
            "targets": [],
            "fallback_used": False,
            "llm_parsed": False,
            "original_query": user_query,
        }
        
        # Level 1: LLM 解析
        llm_result = self._try_llm_parse(user_query)
        if llm_result is not None:
            result.update(llm_result)
            result["llm_parsed"] = True
            return result
        
        # Level 2: 关键词匹配 fallback
        keyword_result = self._fallback_keyword_match(user_query)
        if keyword_result is not None:
            result.update(keyword_result)
            result["fallback_used"] = True
            return result
        
        # Level 3: 默认降级
        default_channel = PushChannelsConfig.get_default_channel()
        result["channel"] = default_channel
        result["fallback_used"] = True
        
        return result

    def send_report_to_channel(
        self,
        *,
        channel: str,
        targets: List[str],
        report_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        发送报告到指定渠道
        
        Args:
            channel: 渠道类型 ("wechat" | "dingtalk" | "email" | "none")
            targets: 目标列表（群 ID 或邮箱）
            report_data: 报告数据
                - project_name
                - total_cost
                - report_file_name
                - report_storage_path
                - generated_at
                - download_url
        
        Returns:
            {
                "success": bool,
                "channel": str,
                "sent_to": List[str],
                "message": str,
                "error": Optional[str],
            }
        """
        # channel = "none" 时，不发送，只返回
        if channel == "none":
            return {
                "success": True,
                "channel": "none",
                "sent_to": [],
                "message": "报告已生成，请在网页端查看和下载。",
                "error": None,
            }
        
        # 检查渠道是否启用
        if not PushChannelsConfig.is_channel_enabled(channel):
            return {
                "success": False,
                "channel": channel,
                "sent_to": [],
                "message": f"推送渠道 {channel} 未启用",
                "error": "Channel not enabled",
            }
        
        # 根据渠道分发
        if channel == "wechat":
            return self._send_to_wechat(targets, report_data)
        elif channel == "dingtalk":
            return self._send_to_dingtalk(targets, report_data)
        elif channel == "email":
            return self._send_to_email(targets, report_data)
        else:
            return {
                "success": False,
                "channel": channel,
                "sent_to": [],
                "message": f"不支持的推送渠道: {channel}",
                "error": "Unknown channel",
            }

    # ===============================
    # LLM 解析（私有方法）
    # ===============================

    def _try_llm_parse(self, user_query: str) -> Optional[Dict[str, Any]]:
        """
        尝试使用 LLM 解析用户意图
        
        Returns:
            成功: {"channel": str, "targets": List[str]}
            失败: None
        """
        def build_prompt(user_input: str) -> str:
            return f"""
            你是一个企业级结构化信息抽取助手。
            从用户输入中提取以下字段：

            "channel": "wechat | dingtalk | email | none",  # 用户希望使用的推送渠道
            "targets": ["目标ID或邮箱", ...]  # 推送目标的ID或者邮箱，可选，如果用户指定了具体目标
            规则：
            1. 如果任何字段不存在，返回 null
            2. channel 必须是给定的字符串之一，wechat | dingtalk | email | none。none代表用户不希望使用自动推送
            3. 只输出 JSON
            4. 不要解释，不要添加额外内容

            用户输入：
            "{user_input}"
            """
            
        client = OpenAI(
        api_key="none",
        base_url="http://localhost:11434/v1"
    )    
        def call_qwen(user_input: str) -> ExtractedPublishInfo:
            #异步调用每次都会创建event loop,关闭event loop,重建loop，开销大，费时多。

            prompt = build_prompt(user_input)

            response = client.chat.completions.create(
                model="qwen2.5:7b",
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
            )

            content = response.choices[0].message.content or "{}"
            parsed = json.loads(content)

            return ExtractedPublishInfo(**parsed)  
    
        try:
            extracted_info = call_qwen(user_query)
            result = {"channel": extracted_info.channel, 
                    "targets": extracted_info.targets}
            return result
            
        except Exception:
            return None

    # ===============================
    # 关键词匹配 fallback（私有方法）
    # ===============================

    def _fallback_keyword_match(self, user_query: str) -> Optional[Dict[str, Any]]:
        """
        关键词匹配 fallback
        
        Returns:
            匹配成功: {"channel": str, "targets": List[str]}
            无匹配: None
        """
        query_lower = user_query.lower()
        keyword_mapping = PushChannelsConfig.get_keyword_mapping()
        
        # 按优先级顺序检查关键词
        for mapping in keyword_mapping:
            keywords = mapping.get("keywords", [])
            for keyword in keywords:
                if keyword.lower() in query_lower:
                    channel = mapping["channel"]
                    targets = PushChannelsConfig.get_channel_targets(channel)
                    return {
                        "channel": channel,
                        "targets": [t.get("id") or t.get("email", "") for t in targets],
                    }
        
        return None

    # ===============================
    # 企业微信发送（私有方法）
    # ===============================

    def _send_to_wechat(self, targets: List[str], report_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        发送到企业微信
        """
        config = PushChannelsConfig.get_channel_config("wechat")
        if not config:
            return {"success": False,
                    "channel": "wechat",
                    "sent_to": [],
                    "message": "Please configure WeChat channel in push_channels_config.yaml",
                    "error":"WeChat config not found"}
        
        webhook_url = config.get("webhook_url")        
        template = config.get("message_template", "")
        #校验 webhook_url 是否配置
        if not webhook_url:
            return {"success": False, 
                    "channel": "wechat",
                    "sent_to": [],
                    "message": "Please configure WeChat webhook URL in push_channels_config.yaml",
                    "error": "WeChat webhook URL not configured"}
        # 渲染消息模板
        message = template.format(**report_data)
        
        sent_to = []
        errors = []
        
        for target in targets:
            try:
                payload = {
                    "msgtype": "text",
                    "text": {"content": message}
                }
                response = requests.post(webhook_url, json=payload, timeout=10)
                
                if response.status_code == 200:
                    sent_to.append(target)
                else:
                    errors.append(f"{target}: {response.text}")
            except Exception as e:
                errors.append(f"{target}: {str(e)}")
        
        return {
            "success": len(sent_to) > 0,
            "channel": "wechat",
            "sent_to": sent_to,
            "message": f"发送到 {len(sent_to)} 个群" if sent_to else "发送失败",
            "error": "; ".join(errors) if errors else None,
        }

    # ===============================
    # 钉钉发送（私有方法）
    # ===============================

    def _send_to_dingtalk(self, targets: List[str], report_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        发送到钉钉
        """
        config = PushChannelsConfig.get_channel_config("dingtalk")
        if not config:
            return {"success": False, 
                    "channel": "dingtalk",
                    "sent_to": [],
                    "message": "Please configure DingTalk channel in push_channels_config.yaml",
                    "error":"DingTalk config not found",
                    }
        
        webhook_url = config.get("webhook_url")
        template = config.get("message_template", "")
        
        #校验 webhook_url 是否配置
        if not webhook_url:
            return {"success": False, 
                    "channel": "dingtalk",
                    "sent_to": [],
                    "message": "Please configure DingTalk channel in push_channels_config.yaml",
                    "error": "DingTalk webhook URL not configured"}
     
        
        # 渲染消息模板
        message = template.format(**report_data)
        
        sent_to = []
        errors = []
        
        for target in targets:
            try:
                payload = {
                    "msgtype": "text",
                    "text": {"content": message}
                }
                response = requests.post(webhook_url, json=payload, timeout=10)
                
                if response.status_code == 200:
                    sent_to.append(target)
                else:
                    errors.append(f"{target}: {response.text}")
            except Exception as e:
                errors.append(f"{target}: {str(e)}")
        
        return {
            "success": len(sent_to) > 0,
            "channel": "dingtalk",
            "sent_to": sent_to,
            "message": f"发送到 {len(sent_to)} 个群" if sent_to else "发送失败",
            "error": "; ".join(errors) if errors else None,
        }

    # ===============================
    # 邮件发送（私有方法）
    # ===============================

    def _send_to_email(self, targets: List[str], report_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        发送到邮件
        """
        config = PushChannelsConfig.get_channel_config("email")
        if not config:
            return {"success": False, "error": "Email config not found", "sent_to": [], "message": ""}
        
        smtp_server = config.get("smtp_server")
        smtp_port = config.get("smtp_port", 587)
        use_tls = config.get("use_tls", True)
        sender = config.get("sender")
        sender_name = config.get("sender_name", "成本核算系统")
        template = config.get("message_template", "")
        
        #校验smtp_server和sender是否配置
        if not smtp_server:
            return {"success": False, 
                    "channel": "email",
                    "sent_to": [],
                    "message": "Please configure SMTP server in push_channels_config.yaml",
                    "error": "SMTP server not configured"}
        if not sender:
            return {"success": False,
                    "channel": "email",
                    "sent_to": [],
                    "message": "Please configure email sender in push_channels_config.yaml",
                    "error": "Email sender not configured"}
        # 渲染邮件内容
        email_body = template.format(**report_data)
        
        sent_to = []
        errors = []
        
        try:
            # 构建邮件
            msg = MIMEMultipart()
            msg['From'] = f"{sender_name} <{sender}>"
            msg['Subject'] = f"成本核算报告 - {report_data.get('project_name', '')}"
            
            # 添加文本正文
            msg.attach(MIMEText(email_body, 'plain', 'utf-8'))
            
            # 添加报告文件附件（如果存在）
            report_path = report_data.get("report_storage_path")
            if report_path and Path(report_path).exists():
                with open(report_path, 'rb') as f:
                    part = MIMEApplication(
                        f.read(),
                        Name=report_data.get("report_file_name", "report.xlsx")
                    )
                part['Content-Disposition'] = f'attachment; filename="{report_data.get("report_file_name", "report.xlsx")}"'
                msg.attach(part)
            
            # 发送邮件
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                if use_tls:
                    server.starttls()
                # TODO: SMTP 认证（用户名/密码从配置或环境变量读取）
                # server.login(username, password)
                for target in targets:
                    msg['To'] = target
                    server.sendmail(sender, [target], msg.as_string())
                    sent_to.append(target)
                    
        except Exception as e:
            errors.append(f"邮件发送失败: {str(e)}")
        
        return {
            "success": len(sent_to) > 0,
            "channel": "email",
            "sent_to": sent_to,
            "message": f"发送到 {len(sent_to)} 个邮箱" if sent_to else "发送失败",
            "error": "; ".join(errors) if errors else None,
        }
