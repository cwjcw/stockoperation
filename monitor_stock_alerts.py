import argparse
import json
import time
from pathlib import Path

from send_stock_quote import get_stock_quote, send_message


DEFAULT_CONFIG_PATH = Path("stock_alerts.json")
DEFAULT_STATE_PATH = Path(".stock_alert_state.json")


def normalize_stock_code(raw_code: str) -> str:
    code = "".join(ch for ch in str(raw_code) if ch.isdigit())
    if len(code) != 6:
        raise ValueError(f"无效股票代码: {raw_code}")
    return code


def parse_condition(condition: str) -> str:
    normalized = str(condition).strip()
    if normalized not in {">=", "<="}:
        raise ValueError(f"不支持的 condition: {condition}")
    return normalized


def parse_price_entry(stock_code: str, stock_label: str, price_item: dict) -> dict:
    target_price = float(price_item["target_price"])
    condition = parse_condition(price_item.get("condition", ">="))
    item_label = str(price_item.get("label", "")).strip()

    if stock_label and item_label:
        label = f"{stock_label} - {item_label}"
    else:
        label = stock_label or item_label

    return {
        "stock_code": normalize_stock_code(stock_code),
        "target_price": target_price,
        "condition": condition,
        "label": label,
    }


def load_alerts(config_path: Path) -> list[dict]:
    data = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not data:
        raise ValueError("预警配置必须是非空数组")

    alerts = []
    for item in data:
        if "prices" in item:
            stock_code = item["stock_code"]
            stock_label = str(item.get("label", "")).strip()
            prices = item["prices"]
            if not isinstance(prices, list) or not prices:
                raise ValueError(f"股票 {stock_code} 的 prices 必须是非空数组")
            for price_item in prices:
                alerts.append(parse_price_entry(stock_code, stock_label, price_item))
            continue

        alerts.append(
            parse_price_entry(
                item["stock_code"],
                str(item.get("label", "")).strip(),
                item,
            )
        )
    return alerts


def load_state(state_path: Path) -> dict:
    if not state_path.exists():
        return {}
    return json.loads(state_path.read_text(encoding="utf-8"))


def save_state(state_path: Path, state: dict) -> None:
    state_path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def is_triggered(current_price: float, target_price: float, condition: str) -> bool:
    if condition == ">=":
        return current_price >= target_price
    return current_price <= target_price


def build_alert_message(alert: dict, quote: dict) -> str:
    label_line = f"预警名称：{alert['label']}\n" if alert["label"] else ""
    return (
        "股票价格触发预警\n"
        f"{label_line}"
        f"股票代码：{quote['code']}\n"
        f"股票名称：{quote['name']}\n"
        f"触发条件：当前价格 {alert['condition']} {alert['target_price']:.2f}\n"
        f"当前价格：{quote['price']}\n"
        f"换手率：{quote['turnover_rate']}\n"
        f"最高价：{quote['high']}\n"
        f"最低价：{quote['low']}"
    )


def monitor_once(alerts: list[dict], touser: str, state_path: Path) -> int:
    state = load_state(state_path)
    triggered_count = 0

    for alert in alerts:
        alert_key = f"{alert['stock_code']}:{alert['condition']}:{alert['target_price']:.2f}"
        try:
            quote = get_stock_quote(alert["stock_code"])
            current_price = float(quote["price"])
            triggered = is_triggered(current_price, alert["target_price"], alert["condition"])
            already_sent = state.get(alert_key, False)

            if triggered and not already_sent:
                message = build_alert_message(alert, quote)
                send_message(message, touser)
                state[alert_key] = True
                triggered_count += 1
                print(f"已触发并发送: {alert_key}")
            elif not triggered and already_sent:
                state[alert_key] = False
                print(f"已重置预警状态: {alert_key}")
            else:
                print(
                    f"未触发: {alert_key}, current={current_price:.2f}, "
                    f"target={alert['target_price']:.2f}"
                )
        except Exception as exc:
            print(f"检查失败: {alert_key}, error={exc}")

    save_state(state_path, state)
    return triggered_count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="监控股票价格并在触发时发送企业微信消息")
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help=f"预警配置文件路径，默认 {DEFAULT_CONFIG_PATH}",
    )
    parser.add_argument(
        "--state-file",
        default=str(DEFAULT_STATE_PATH),
        help=f"预警状态文件路径，默认 {DEFAULT_STATE_PATH}",
    )
    parser.add_argument(
        "--touser",
        default="CuiWeiJie",
        help="企业微信用户名，默认 CuiWeiJie",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="轮询间隔秒数，默认 60",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="只检查一次，不循环监控",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config_path = Path(args.config)
    state_path = Path(args.state_file)
    alerts = load_alerts(config_path)

    if args.once:
        monitor_once(alerts, args.touser, state_path)
        return 0

    while True:
        try:
            monitor_once(alerts, args.touser, state_path)
        except Exception as exc:
            print(f"本轮检查失败: {exc}")
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
