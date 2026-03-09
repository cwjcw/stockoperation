import argparse
import math
from pathlib import Path
import sys

import akshare as ak

try:
    from wechat import WeChatPusher
except ModuleNotFoundError:
    fallback_path = Path(r"E:\code\basic_code")
    if str(fallback_path) not in sys.path:
        sys.path.append(str(fallback_path))
    from wechat import WeChatPusher


DEFAULT_STOCK_CODE = "000001"


def normalize_stock_code(raw_code: str) -> str:
    code = "".join(ch for ch in raw_code if ch.isdigit())
    if len(code) != 6:
        raise ValueError(f"无效股票代码: {raw_code}")
    return code


def to_xq_symbol(stock_code: str) -> str:
    if stock_code.startswith(("600", "601", "603", "605", "688", "689")):
        return f"SH{stock_code}"
    if stock_code.startswith(("000", "001", "002", "003", "300", "301")):
        return f"SZ{stock_code}"
    if stock_code.startswith(("430", "440", "830", "831", "832", "833", "834", "835", "836", "837", "838", "839", "870", "871", "872", "873", "874", "875", "876", "877", "878", "879")):
        return f"BJ{stock_code}"
    if stock_code.startswith(("4", "8")):
        return f"BJ{stock_code}"
    raise ValueError(f"无法判断交易所，请确认股票代码: {stock_code}")


def format_value(value, suffix: str = "") -> str:
    if value is None:
        return "--"
    try:
        if isinstance(value, float) and math.isnan(value):
            return "--"
        numeric = float(value)
    except (TypeError, ValueError):
        text = str(value).strip()
        return text if text else "--"
    return f"{numeric:.2f}{suffix}"


def get_stock_quote(stock_code: str) -> dict:
    symbol = to_xq_symbol(stock_code)
    df = ak.stock_individual_spot_xq(symbol=symbol, timeout=10)
    quote_map = dict(zip(df["item"], df["value"]))
    return {
        "code": str(quote_map.get("代码", symbol)),
        "name": str(quote_map.get("名称", "--")),
        "price": format_value(quote_map.get("现价")),
        "turnover_rate": format_value(quote_map.get("周转率"), "%"),
        "high": format_value(quote_map.get("最高")),
        "low": format_value(quote_map.get("最低")),
    }


def build_message(quote: dict) -> str:
    return (
        "股票实时信息\n"
        f"股票代码：{quote['code']}\n"
        f"股票名称：{quote['name']}\n"
        f"当前价格：{quote['price']}\n"
        f"换手率：{quote['turnover_rate']}\n"
        f"最高价：{quote['high']}\n"
        f"最低价：{quote['low']}"
    )


def send_message(message: str, touser: str) -> dict:
    pusher = WeChatPusher()
    response = pusher.send_app_msg(message, msg_type="text", touser=touser)
    if not response:
        raise RuntimeError("企业微信发送失败，未拿到响应")
    if response.get("errcode") != 0:
        raise RuntimeError(
            f"企业微信发送失败: errcode={response.get('errcode')} errmsg={response.get('errmsg')}"
        )
    return response


def send_stock_quote(stock_code: str, touser: str) -> dict:
    quote = get_stock_quote(stock_code)
    message = build_message(quote)
    return send_message(message, touser)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="发送股票实时信息到企业微信")
    parser.add_argument(
        "stock_code",
        nargs="?",
        default=DEFAULT_STOCK_CODE,
        help=f"6 位股票代码，默认 {DEFAULT_STOCK_CODE}",
    )
    parser.add_argument(
        "--touser",
        default="CuiWeiJie",
        help="企业微信用户名，默认 CuiWeiJie",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        stock_code = normalize_stock_code(args.stock_code)
        response = send_stock_quote(stock_code, args.touser)
    except Exception as exc:
        print(f"执行失败: {exc}")
        return 1

    print(f"发送完成: {response}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
