import os
import time
import logging
import traceback
from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType
from py_clob_client.order_builder.constants import BUY, SELL

# 加载环境变量
load_dotenv()

# 配置日志（修复语法错误，使用正确格式）
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

class PolymarketCopyBot:
    def __init__(self):
        # 必填环境变量检查
        required_envs = ["BUILDER_API_KEY", "BUILDER_API_SECRET", "BUILDER_API_PASSPHRASE", "PROFILE_ADDRESS"]
        missing_envs = [env for env in required_envs if not os.getenv(env)]
        if missing_envs:
            raise ValueError(f"缺少必填环境变量: {', '.join(missing_envs)}")
        
        # 初始化API凭证
        self.api_key = os.getenv("BUILDER_API_KEY")
        self.api_secret = os.getenv("BUILDER_API_SECRET")
        self.passphrase = os.getenv("BUILDER_API_PASSPHRASE")
        self.funder = os.getenv("PROFILE_ADDRESS")
        
        # 解析跟单交易员地址（验证格式：0x开头，42字符）
        self.copy_traders = []
        traders_str = os.getenv("COPY_TRADERS", "").strip()
        if traders_str:
            for addr in traders_str.split(","):
                addr_clean = addr.strip()
                if addr_clean.startswith("0x") and len(addr_clean) == 42:
                    self.copy_traders.append(addr_clean)
                elif addr_clean:  # 非空但无效地址
                    logger.warning(f"跳过无效交易员地址: {addr_clean} (需0x开头42字符)")
        logger.info(f"初始化完成，有效跟单地址数: {len(self.copy_traders)}")
        
        # 风控参数（带默认值）
        self.max_daily_volume = float(os.getenv("MAX_DAILY_VOLUME_USD", "10"))
        self.max_position_size = float(os.getenv("MAX_POSITION_SIZE_USD", "5"))
        self.copy_ratio = float(os.getenv("COPY_RATIO", "0.1"))
        self.dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
        
        # 初始化客户端
        self._init_client()
        
        # 运行状态变量
        self.daily_total = 0.0  # 当日累计交易量
        self.last_reset = time.time()  # 上次重置时间（时间戳）
        self.copied_trades = set()  # 已复制交易哈希集合

    def _init_client(self):
        """初始化Polymarket CLOB客户端"""
        host = "https://clob.polymarket.com"  # 英文引号
        chain_id = 137  # Polygon主网
        try:
            self.client = ClobClient(
                host=host,
                key=None,  # 若需签名交易可传入私钥
                chain_id=chain_id,
                funder=self.funder
            )
            # 设置API凭证（修复字典语法：冒号+英文引号）
            self.client.set_api_creds({
                "api_key": self.api_key,
                "api_secret": self.api_secret,
                "api_passphrase": self.passphrase
            })
            logger.info("CLOB客户端初始化成功")
        except Exception as e:
            logger.error(f"客户端初始化失败: {str(e)}")
            raise  # 抛出异常终止启动

    def reset_daily_if_needed(self):
        """检查并重置每日交易限额（修复逻辑错误）"""
        current_time = time.time()
        if current_time - self.last_reset > 24 * 3600:  # 超过24小时（86400秒）
            self.daily_total = 0.0
            self.last_reset = current_time
            logger.info("每日交易限额已重置")

    def get_trader_activity(self, trader_address):
        """获取交易员活动（待对接真实API，当前返回空列表）"""
        # TODO: 接入Polymarket API获取真实交易记录（如GraphQL/REST）
        # 示例伪代码：
        # response = requests.get(f"https://api.polymarket.com/v1/traders/{trader_address}/trades")
        # return response.json().get("trades", [])
        logger.debug(f"未实现真实API对接，交易员 {trader_address} 返回空活动")
        return []

    def execute_trade(self, trade_data):
        """执行跟单交易（模拟/实盘逻辑分离）"""
        try:
            amount = trade_data.get("amount", 0.0)
            market_id = trade_data.get("market_id")
            side = BUY if trade_data.get("side") == "buy" else SELL
            
            # 风控检查：单笔不超过最大仓位，当日累计不超限额
            if amount > self.max_position_size:
                logger.warning(f"交易金额 {amount} 超单笔限额 {self.max_position_size}，跳过")
                return
            if self.daily_total + amount > self.max_daily_volume:
                logger.warning(f"当日累计 {self.daily_total}+{amount} 超限额 {self.max_daily_volume}，跳过")
                return
            
            if self.dry_run:
                # 模拟模式：记录日志不执行
                logger.info(f"[模拟] 跟单: 交易员={trade_data.get('trader')}, 市场={market_id}, 方向={side}, 金额={amount} USD")
                self.daily_total += amount  # 模拟累计
            else:
                # 实盘模式：调用CLOB API下单（需补充订单构建逻辑）
                order_args = OrderArgs(
                    price=trade_data.get("price"),
                    size=amount * self.copy_ratio,  # 按比例跟单
                    side=side,
                    market_id=market_id
                )
                order = self.client.create_order(order_args)
                logger.info(f"[实盘] 下单成功: 订单ID={order['id']}, 金额={amount} USD")
                self.daily_total += amount
                self.copied_trades.add(trade_data["tx_hash"])  # 记录已复制交易
        except Exception as e:
            logger.error(f"执行交易失败: {str(e)}\n交易数据: {trade_data}", exc_info=True)

    def run_cycle(self):
        """单次扫描周期：检查交易员活动并执行跟单"""
        self.reset_daily_if_needed()  # 先检查重置限额
        if not self.copy_traders:
            logger.warning("无有效跟单地址，跳过本次扫描")
            return
        
        for trader in self.copy_traders:
            try:
                logger.debug(f"扫描交易员: {trader}")
                activities = self.get_trader_activity(trader)
                if not activities:
                    continue
                
                for trade in activities:
                    tx_hash = trade.get("tx_hash")
                    if not tx_hash or tx_hash in self.copied_trades:
                        continue  # 跳过无哈希或已复制交易
                    self.execute_trade(trade)  # 执行跟单
            except Exception as e:
                logger.error(f"处理交易员 {trader} 异常: {str(e)}", exc_info=True)
                continue  # 单个交易员失败不影响其他

    def run(self):
        """主循环：持续扫描并执行跟单"""
        logger.info(f"跟单机器人启动 | 模式: {'模拟' if self.dry_run else '实盘'} | 扫描间隔: 60秒")
        logger.info(f"风控参数: 每日限额=${self.max_daily_volume}, 单笔最大=${self.max_position_size}, 跟单比例={self.copy_ratio}")
        while True:
            try:
                self.run_cycle()
                logger.debug("扫描完成，等待60秒...")
                time.sleep(60)
            except KeyboardInterrupt:
                logger.info("用户中断，程序退出")
                break
            except Exception as e:
                logger.error(f"主循环异常: {str(e)}", exc_info=True)
                time.sleep(60)  # 异常后等待重试

if __name__ == "__main__":
    try:
        bot = PolymarketCopyBot()
        bot.run()
    except Exception as e:
        logger.exception("程序启动失败")
        # 保持容器运行（如需）
        while True:
            time.sleep(3600)
