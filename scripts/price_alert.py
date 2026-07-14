#!/usr/bin/env python3
"""轻量级价格预警脚本 - 支持多规则同时触发"""
import os
import json
import urllib.request
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timezone, timedelta, time
import sys

# 设置北京时间时区
BJT = timezone(timedelta(hours=8))

def is_trading_time():
    """
    检查当前是否在A股有效交易时段（北京时间）
    范围：9:15-11:30, 13:00-15:00
    """
    now = datetime.now(BJT).time()
    
    # 上午时段 9:15 - 11:30
    morning = time(9, 15) <= now <= time(11, 30)
    # 下午时段 13:00 - 15:00
    afternoon = time(13, 0) <= now <= time(15, 0)
    
    return morning or afternoon

def fetch_price(code):
    """获取股票实时价格"""
    prefix = 'sh' if code.startswith('6') else 'sz'
    url = f"https://qt.gtimg.cn/q={prefix}{code}"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read().decode('gbk', errors='ignore')
        value = data.split('=', 1)[1].strip('" ;\n')
        fields = value.split('~')
        return fields[1], float(fields[3])  # name, price
    except Exception as e:
        print(f"获取价格失败: {e}")
        return None, 0.0

def send_email(subject, content):
    """发送邮件"""
    sender = os.environ.get('EMAIL_SENDER', '')
    password = os.environ.get('EMAIL_PASSWORD', '')
    receivers = os.environ.get('EMAIL_RECEIVERS', '')
    
    if not all([sender, password, receivers]):
        print(f"邮箱配置不完整")
        return False
    
    msg = MIMEText(content, 'plain', 'utf-8')
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = receivers
    
    try:
        with smtplib.SMTP_SSL('smtp.qq.com', 465) as smtp:
            smtp.login(sender, password)
            smtp.sendmail(sender, receivers.split(','), msg.as_string())
        print(f"  ✓ 邮件已发送")
        return True
    except Exception as e:
        print(f"  ✗ 邮件发送失败: {e}")
        return False

def main():
    now = datetime.now(BJT)
    
    # === 核心修改：非交易时段直接退出 ===
    if not is_trading_time():
        print(f"⚠️ 跳过执行 | 当前时间 {now.strftime('%H:%M')} 不在交易时段 (9:15-11:30, 13:00-15:00)")
        sys.exit(0)
    # ================================

    # 检查是否在周末
    weekday = now.weekday()
    if weekday >= 5:
        print("周末，跳过")
        return
    
    # 获取配置
    stock_list = os.environ.get('STOCK_LIST', '')
    rules_json = os.environ.get('AGENT_EVENT_ALERT_RULES_JSON', '[]')
    
    if not stock_list:
        print("STOCK_LIST 未配置")
        return
    
    print(f"[{now.strftime('%H:%M:%S')}] 检查股票: {stock_list}")
    
    # 解析预警规则
    try:
        rules = json.loads(rules_json)
    except json.JSONDecodeError as e:
        print(f"预警规则 JSON 解析错误: {e}")
        return
    
    # 按股票分组，收集所有触发的预警
    all_alerts = {}  # {stock_code: {"name": name, "price": price, "alerts": []}}
    
    for stock_code in stock_list.split(','):
        stock_code = stock_code.strip()
        if not stock_code:
            continue
        
        try:
            name, price = fetch_price(stock_code)
            if price == 0.0:
                continue
                
            print(f"  {name}({stock_code}): {price:.2f}")
            
            # 检查该股票的所有预警规则
            stock_alerts = []
            for rule in rules:
                if rule.get('stock_code') != stock_code:
                    continue
                
                alert_type = rule.get('alert_type')
                
                if alert_type == 'price_cross':
                    target = rule.get('price', 0)
                    direction = rule.get('direction', 'above')
                    if direction == 'above' and price >= target:
                        stock_alerts.append(f"突破 {target}")
                    elif direction == 'below' and price <= target:
                        stock_alerts.append(f"跌破 {target}")
                
                elif alert_type == 'price_change_percent':
                    # 需要昨收价，这里简化处理
                    pass
                
                elif alert_type == 'volume_spike':
                    # 成交量检查需要历史数据，这里简化
                    pass
            
            # 收集该股票的所有触发预警
            if stock_alerts:
                all_alerts[stock_code] = {
                    "name": name,
                    "price": price,
                    "alerts": stock_alerts
                }
                print(f"    触发: {', '.join(stock_alerts)}")
            else:
                print(f"    未触发预警")
        
        except Exception as e:
            print(f"  ✗ 错误: {e}")
    
    # 统一发送所有触发的预警通知
    if all_alerts:
        # 构建通知内容
        lines = []
        for code, info in all_alerts.items():
            lines.append(f"【{info['name']}({code})】")
            lines.append(f"当前价格: {info['price']:.2f}")
            lines.append(f"触发条件: {', '.join(info['alerts'])}")
            lines.append("")
        
        subject = f"【股价预警】{len(all_alerts)}只股票触发预警"
        content = "\n".join(lines) + f"时间: {now.strftime('%Y-%m-%d %H:%M:%S')}"
        
        send_email(subject, content)
        print(f"\n共 {len(all_alerts)} 只股票触发预警，已发送通知")

if __name__ == '__main__':
    main()
