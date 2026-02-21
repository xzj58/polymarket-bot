import os
import time
import logging
import traceback
from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType
from py_clob_client.order_builder.constants import BUY, SELL

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

class PolymarketCopyBot:
    def __init__(self):
        # 必填环境变量检查
        required = ["BUILDER_API_KEY", "BUILDER_API_SECRET", "BUILDER_API_PASSPHRASE", "PROFILE_ADDRESS"]
        missing = [v for v in required if not os.getenv(v)]
        if missing:
            raise ValueError(f"缺少环境变量: {missing}")

        self.api_key = os.getenv("BUILDER_API_KEY")
        self.api_secret = os.getenv("BUILDER_API_SECRET")
        self.passphrase = os.getenv("BUILDER_API_PASSPHRASE")
        self.funder = os.getenv("PROFILE_ADDRESS")
        traders_str = os.getenv("COPY_TRADERS", "")
        # 解析地址，去除空项并验证格式
        self.copy_traders = []
        for addr in traders_str.split(","):
            addr = addr.strip()
            if addr and addr.startswith("0x") and len(addr) == 42:
                self.copy_traders.append(addr)
            elif addr:
                logging.warning(f"跳过无效地址: {addr}")

        self.max_daily_volume = float(os.getenv("MAX_DAILY_VOLUME_USD", 10))
        self.max_position_size = float(os.getenv("MAX_POSITION_SIZE_USD", 5))
        self.copy_ratio = float(os.getenv("COPY_RATIO", 0.1))
        self.dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
        self.auto_redeem = os.getenv("AUTO_REDEEM", "true").lower() == "true"
        self.rpc_url = os.getenv("RPC_URL", "https://polygon-rpc.com")

        # 初始化客户端
        host = "https://clob.polymarket.com"
        chain_id = 137
        try:
            self.client = ClobClient(host, key=self.api_key, chain_id=chain_id, funder=self.funder)
            self.client.set_api_creds({
                "api_key": self.api_key,
                "api_secret": self.api_secret,
                "api_passphrase": self.passphrase
            })
            logging.info("Polymarket 客户端初始化成功")
        except Exception as e:
            logging.error(f"客户端初始化失败: {e}")
            raise

        self.daily_total = 0
        self.last_reset = time.time()
        self.copied_trades = set()

        logging.info(f"初始化完成，有效跟单地址数: {len(self.copy_traders)}")
        logging.info(f"风控: 每日限额 ${self.max_daily_volume}, 单笔最大 ${self.max_position_size}, 跟单比例 {self.copy_ratio}")
        logging.info(f"当前模式: {'模拟' if self.dry_run else '实盘'}")

    def reset_daily_if_needed(self):
        now = time.time()
        if now - self.last_reset > 24 * 3600:
            self.daily_total = 0
            self.last_reset = now
            logging.info("每日限额已重置")

    def get_trader_activity(self, trader):
        # TODO: 接入真实API获取交易记录，目前返回空列表防止出错
        return []

    def execute_trade(self, trade):
        if self.dry_run:
            logging.info(f"[模拟] 跟单: 交易员 {trade.get('trader')} 金额 {trade.get('amount',0)} 美元")
            self.daily_total += trade.get('amount', 0)
        else:
            logging.info("实盘功能未启用")

    def run_cycle(self):
        self.reset_daily_if_needed()
        for trader in self.copy_traders:
            try:
                logging.debug(f"检查交易员 {trader}")
                activities = self.get_trader_activity(trader)
                for trade in activities:
                    tx_hash = trade.get("tx_hash")
                    if tx_hash in self.copied_trades:
                        continue
                    self.execute_trade(trade)
            except Exception as e:
                logging.error(f"处理交易员 {trader} 时出错: {e}")
                continue

    def run(self):
        logging.info("跟单机器人启动，主循环开始")
        while True:
            try:
                self.run_cycle()
                logging.info("等待60秒后再次扫描...")
                time.sleep(60)
            except Exception as e:
                logging.error(f"主循环异常: {e}")
                traceback.print_exc()
                time.sleep(60)

if __name__ == "__main__":
    try:
        bot = PolymarketCopyBot()
        bot.run()
    except Exception as e:
        logging.exception("程序启动失败")
        traceback.print_exc()
        # 保持容器运行，便于查看日志
        while True:
            time.sleep(60)
