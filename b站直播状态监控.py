import requests
import time
import json
import logging
import os
import sys
from typing import Optional, Dict, Any

if sys.platform == "win32":
    # Windows
    os.system(f"title b站直播状态监控.exe -by 小段_d https://space.bilibili.com/105116728 使用此程序时请声明来源")
elif sys.platform in ["linux", "darwin"]:
    # Linux 和 macOS
    sys.stdout.write(f"\033]0;b站直播状态监控.exe -by 小段_d https://space.bilibili.com/105116728 使用此程序时请声明来源\007")
    sys.stdout.flush()


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bilibili_live_monitor.log",encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class BilibiliLiveMonitor:
    def __init__(self, room_id: str, area_id: int, cookie: str, check_interval: int = 30, retry_interval: int = 10, max_retries: int = 5):
        """
        初始化B站直播监控器
        
        :param room_id: 直播间ID
        :param area_id: 分区ID
        :param cookie: 登录Cookie
        :param check_interval: 检查间隔(秒)
        :param retry_interval: 重试间隔(秒)
        :param max_retries: 最大重试次数
        """
        self.room_id = room_id
        self.area_id = area_id
        self.cookie = cookie
        self.check_interval = check_interval
        self.retry_interval = retry_interval
        self.max_retries = max_retries
        self.csrf_token = self._extract_csrf_token()
        self.is_running = False
        
    def _extract_csrf_token(self) -> str:
        """从Cookie中提取CSRF token"""
        csrf = ""
        for item in self.cookie.replace(' ', '').split(';'):
            if '=' in item:
                key, value = item.split('=', 1)
                if key == 'bili_jct':
                    csrf = value
                    break
        if not csrf:
            raise ValueError("未在Cookie中找到bili_jct(CSRF token)")
        return csrf
    
    def is_live_open(self) -> bool:
        """检查直播是否开启"""
        try:
            url = f"https://api.live.bilibili.com/xlive/web-room/v1/index/getInfoByRoom?room_id={self.room_id}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Cookie": self.cookie,
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data['code'] != 0:
                logger.error(f"检查直播状态失败: {data.get('message', '未知错误')}")
                return False
            
            # 检查直播状态，live_status == 1 表示直播中
            live_status = data['data']['room_info']['live_status']
            return live_status == 1
            
        except requests.exceptions.RequestException as e:
            logger.error(f"网络请求错误: {e}")
            return False
        except Exception as e:
            logger.error(f"检查直播状态时出错: {e}")
            return False
    
    def start_live(self) -> Optional[Dict[str, Any]]:
        """开启直播"""
        try:
            url = "https://api.live.bilibili.com/room/v1/Room/startLive"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Origin": "https://link.bilibili.com",
                "Referer": "https://link.bilibili.com/p/center/index",
                "Cookie": self.cookie,
            }
            data = {
                "room_id": self.room_id,
                "platform": "pc_link",
                "area_v2": self.area_id,
                "csrf_token": self.csrf_token,
                "csrf": self.csrf_token,
                "ts": int(time.time()),
                "version": "7.19.0.1000",
                "build": "1000",
                "appkey": "aae92bc66f3edfab",
            }
            response = requests.post(url, headers=headers, data=data, timeout=10)
            response.raise_for_status()
            result = response.json()
            
            if result["code"] != 0:
                logger.error(f"开启直播失败: {result.get('message', '未知错误')}")
                return None
            
            logger.info("直播开启成功")
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"网络请求错误: {e}")
            return None
        except Exception as e:
            logger.error(f"开启直播时出错: {e}")
            return None
    
    def check_and_restart_live(self):
        """检查并在需要时重启直播"""
        if not self.is_live_open():
            logger.warning("检测到直播未开启，正在尝试重启...")
            
            for attempt in range(self.max_retries):
                logger.info(f"尝试重启直播... (尝试 {attempt + 1}/{self.max_retries})")
                result = self.start_live()
                if result:
                    logger.info("直播重启成功")
                    return True
                if attempt < self.max_retries - 1:  # 如果不是最后一次尝试
                    logger.warning(f"重启直播失败，{self.retry_interval}秒后重试...")
                    time.sleep(self.retry_interval)

            logger.error(f"在 {self.max_retries} 次尝试后仍未能重启直播，程序退出")
            self.stop()  # 停止监控
            return False
        else:
            logger.info("直播状态正常")
            return True
    
    def run(self):
        """运行监控循环"""
        self.is_running = True
        logger.info("直播监控已启动")
        try:
            while self.is_running:
                self.check_and_restart_live()
                time.sleep(self.check_interval)  # 按配置的检查间隔等待
        except KeyboardInterrupt:
            logger.info("监控已手动停止")
        finally:
            self.is_running = False
            logger.info("直播监控已结束")
    
    def stop(self):
        """停止监控"""
        self.is_running = False


def load_config(config_file: str = "config.json") -> dict:
    """从配置文件加载设置"""
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"配置文件 {config_file} 不存在")
        raise
    except json.JSONDecodeError:
        logger.error(f"配置文件 {config_file} 格式错误")
        raise


def main():
    """主函数"""
    try:
        # 加载配置
        config = load_config()
        room_id = config.get("room_id", "")
        area_id = config.get("area_id", 610)
        cookie = config.get("cookie", "")
        check_interval = config.get("check_interval", 30)
        retry_interval = config.get("retry_interval", 10)
        max_retries = config.get("max_retries", 5)  # 修改为最大重试次数
        
        if not room_id or not cookie:
            raise ValueError("请确保配置文件中包含room_id和cookie")
        
        # 创建监控器实例
        monitor = BilibiliLiveMonitor(room_id, area_id, cookie, check_interval, retry_interval, max_retries)
        
        # 启动监控
        monitor.run()
        
    except Exception as e:
        logger.error(f"程序启动失败: {e}")
        logger.info("请确保已创建config.json文件，并包含以下内容:")
        logger.info('{"room_id": "你的直播间ID", "area_id": 分区ID, "cookie": "你的Cookie", "check_interval": 检测直播状态时间间隔, "retry_interval": 失败重启时间间隔, "max_retries": 最大重试次数}')


if __name__ == "__main__":
    main()