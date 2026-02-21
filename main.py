import os
import time
import logging
from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType
from py_clob_client.order_builder.constants import BUY, SELL

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class PolymarketCopyBot:
    def __init__(self):
        # 从环境变量读取配置
        self.api_key = os.getenv("BUILDER_API_KEY")
        self.api_secret = os.getenv("BUILDER_API_SECRET")
        self.passphrase = os.getenv("BUILDER_API_PASSPHRASE")
        self.funder = os.getenv("PROFILE_ADDRESS")
        traders = os.getenv("COPY_TRADERS", "")
        self.copy_traders = [t.strip() for t in traders.split(",") if t.strip()] if traders else []
        self.max_daily_volume = float(os.getenv("MAX_DAILY_VOLUME_USD", 10))
        self.max_position_size = float(os.getenv("MAX_POSITION_SIZE_USD", 5))
        self.copy_ratio = float(os.getenv("COPY_RATIO", 0.1))
        self.dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
        self.auto_redeem = os.getenv("AUTO_REDEEM", "true").lower() == "true"
        self.rpc_url = os.getenv("RPC_URL", "https://polygon-rpc.com")

        # 初始化客户端
        host = "https://clob.polymarket.com"
        chain_id = 137
        self.client = ClobClient(host, key=self.api_key, chain_id=chain_id, funder=self.funder)
        self.client.set_api_creds({
            "api_key": self.api_key,
            "api_secret": self.api_secret,
            "api_passphrase": self.passphrase
        })

        self.daily_total = 0
        self.last_reset = time.time()
        self.copied_trades = set()

        logging.info(f"初始化完成，跟单地址: {self.copy_traders}")
        logging.info(f"风控: 每日限额 ${self.max_daily_volume}, 单笔最大 ${self.max_position_size}, 跟单比例 {self.copy_ratio}")
        if self.dry_run:
            logging.info("当前为模拟模式(DRY_RUN)，不会实际下单")

    def reset_daily_if_needed(self):
        now = time.time()
        if now - self.last_reset > 24 * 3600:
            self.daily_total = 0
            self.last_reset = now
            logging.info("每日限额已重置")

    def get_trader_activity(self, trader):
        # 暂时返回空列表，避免API调用出错（后续可扩展）
        return []

    def execute_trade(self, trade):
        # 模拟模式下只打印日志
        if self.dry_run:
            logging.info(f"模拟跟单: 交易员 {trade.get('trader')} 买入 {trade.get('amount')} 美元")
            self.daily_total += trade.get('amount', 0)
            return

        # 实盘逻辑（暂不启用，先保持模拟）
        logging.info("实盘功能暂未启用")

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
                logging.error(f"处理交易员 {trader} 时出错: {e}", exc_info=True)
                continue

    def run(self):
        logging.info("跟单机器人启动")
        while True:
            try:
                self.run_cycle()
                logging.info("等待60秒后再次扫描...")
                time.sleep(60)
            except Exception as e:
                logging.error(f"主循环发生未捕获异常: {e}", exc_info=True)
                time.sleep(60)

if __name__ == "__main__":
    bot = PolymarketCopyBot()
    bot.run()
