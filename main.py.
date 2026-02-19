import os
import time
import logging
from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType
from py_clob_client.order_builder.constants import BUY, SELL

load_dotenv()

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class PolymarketCopyBot:
    def __init__(self):
        # 从环境变量读取配置
        self.api_key = os.getenv("BUILDER_API_KEY")
        self.api_secret = os.getenv("BUILDER_API_SECRET")
        self.passphrase = os.getenv("BUILDER_API_PASSPHRASE")
        self.funder = os.getenv("PROFILE_ADDRESS")
        self.copy_traders = os.getenv("COPY_TRADERS", "").split(",")
        self.max_daily_volume = float(os.getenv("MAX_DAILY_VOLUME_USD", 10))
        self.max_position_size = float(os.getenv("MAX_POSITION_SIZE_USD", 5))
        self.copy_ratio = float(os.getenv("COPY_RATIO", 0.1))
        self.dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
        self.auto_redeem = os.getenv("AUTO_REDEEM", "true").lower() == "true"
        self.rpc_url = os.getenv("RPC_URL", "https://polygon-rpc.com")

        # 初始化客户端
        host = "https://clob.polymarket.com"
        chain_id = 137
        # 使用 API 密钥方式，不需要私钥
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
        """
        获取交易员最近交易记录
        需要调用 Polymarket API 获取交易历史
        TODO: 你需要根据实际情况实现此方法
        暂时返回空列表，机器人不会实际跟单
        """
        # 这里需要你根据文档实现获取交易记录的逻辑
        # 示例返回空（可自行扩展）
        return []

    def execute_trade(self, trade):
        token_id = trade.get("token_id")
        side = BUY if trade.get("side") == "BUY" else SELL
        price = float(trade.get("price", 0))
        size = float(trade.get("size", 0))
        trade_amount = price * size

        copy_amount = min(trade_amount * self.copy_ratio, self.max_position_size)
        if copy_amount < 1:
            logging.info(f"跟单金额太小 ({copy_amount} < 1)，跳过")
            return

        # 检查每日限额
        if self.daily_total + copy_amount > self.max_daily_volume:
            logging.warning(f"达到每日限额，当前已用 ${self.daily_total}，尝试跟单 ${copy_amount} 被拒绝")
            return

        logging.info(f"准备跟单: 金额 ${copy_amount}, 价格 {price}, 方向 {'买入' if side==BUY else '卖出'}")

        if self.dry_run:
            logging.info("模拟模式，实际未下单")
            self.daily_total += copy_amount
            self.copied_trades.add(trade.get("tx_hash"))
            return

        # 实际下单
        try:
            order = OrderArgs(
                token_id=token_id,
                price=price,
                size=copy_amount / price,
                side=side
            )
            signed_order = self.client.create_order(order)
            resp = self.client.post_order(signed_order, OrderType.GTC)
            logging.info(f"下单成功: {resp}")
            self.daily_total += copy_amount
            self.copied_trades.add(trade.get("tx_hash"))
        except Exception as e:
            logging.error(f"下单失败: {e}")

    def run_cycle(self):
        self.reset_daily_if_needed()
        for trader in self.copy_traders:
            if not trader.strip():
                continue
            logging.debug(f"检查交易员 {trader}")
            activities = self.get_trader_activity(trader.strip())
            for trade in activities:
                tx_hash = trade.get("tx_hash")
                if tx_hash in self.copied_trades:
                    continue
                self.execute_trade(trade)

    def run(self):
        logging.info("跟单机器人启动")
        while True:
            try:
                self.run_cycle()
                time.sleep(60)  # 每分钟扫描一次
            except Exception as e:
                logging.error(f"循环出错: {e}")
                time.sleep(60)

if __name__ == "__main__":
    bot = PolymarketCopyBot()
    bot.run()
