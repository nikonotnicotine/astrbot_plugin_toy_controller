import re
import asyncio
import aiohttp
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api.provider import LLMResponse

@register("sl278h_controller", "YourName", "SL278H 玩具专版控制器", "1.0.0")
class SL278HControllerPlugin(Star):
    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.config = config

    async def send_to_bridge(self, command_hex: str):
        """将生成的 16 进制字符串发送给中继程序"""
        api_url = self.config.get("toy_api_url", "http://127.0.0.1:8080/command")
        logger.info(f"⚡ 发送 HEX 指令: {command_hex}")
        try:
            async with aiohttp.ClientSession() as session:
                # 把十六进制指令推给本地连接蓝牙的电脑
                await session.post(api_url, json={"hex": command_hex}, timeout=3)
        except Exception as e:
            logger.error(f"连接玩具端失败: {e}")

    @filter.on_llm_response()
    async def on_llm_resp(self, event: AstrMessageEvent, resp: LLMResponse):
        if not resp.completion_text:
            return

        text = resp.completion_text
        
        # 正则匹配三种格式：[stop], [speed:200], [vibrate:3:5]
        pattern = r'\[(stop|speed|vibrate)(?::(\d+))?(?::(\d+))?\]'
        matches = list(re.finditer(pattern, text, re.IGNORECASE))
        
        for match in matches:
            action = match.group(1).lower()
            command_hex = ""

            if action == "stop":
                command_hex = self.config.get("stop_cmd", "55 04 00 00 00 00 AA").replace(" ", "")
                
            elif action == "speed":
                # 获取强度，范围 0-255，默认为 128 (中等)
                intensity = int(match.group(2)) if match.group(2) else 128
                intensity = max(0, min(255, intensity))
                
                # 转为2位十六进制
                int_hex = f"{intensity:02X}"
                template = self.config.get("speed_cmd_template", "55 04 00 00 01 {intensity} AA")
                command_hex = template.replace("{intensity}", int_hex).replace(" ", "")

            elif action == "vibrate":
                # 获取模式(1-8) 和 强度(1-5)
                mode = int(match.group(2)) if match.group(2) else 1
                level = int(match.group(3)) if match.group(3) else 3
                
                mode = max(1, min(8, mode))
                level = max(1, min(5, level))
                
                template = self.config.get("vibrate_cmd_template", "55 03 00 00 {mode} {level} 00")
                command_hex = template.replace("{mode}", f"{mode:02X}").replace("{level}", f"{level:02X}").replace(" ", "")

            logger.info(f"💕 解析动作: {action} -> 组装HEX: {command_hex}")
            asyncio.create_task(self.send_to_bridge(command_hex))

        if matches:
            # 清除标签文本
            clean_text = re.sub(pattern, '', text, flags=re.IGNORECASE).strip()
            resp.completion_text = clean_text