#!/usr/bin/env python3
"""轻量级价格预警脚本"""
import os
import json
import urllib.request
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timezone, timedelta
BJT = timezone(timedelta(hours=8))
def fetch_price(code):
    """获取股票实时价格"""
    prefix = 'sh' if code.startswith('6') else 'sz'
    url = f"https://qt.gtimg.cn/q={prefix}{code}"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = resp.read().decode('gbk', errors='ignore')
    value = data.split('=', 1)[1].strip('" ;\n')
    fields = value.split('~')
    return fields[1], float(fields[3])  # name, price
def send_email(subject, content):
    """发送邮件"""
    sender = os.environ.get('EMAIL_SENDER', '')
    password = os.environ.get('EMAIL_PASSWORD', '')
    receivers = os.environ.get('EMAIL_RECEIVERS', '')
    
    if not all([sender, password, receivers]):
        print(f"邮箱配置不完整: sender={bool(sender)}, password={bool(password)}, receivers={bool(receivers)}")
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
    
    # 检查是否在交易时间
    weekday = now.weekday()
    if weekday >= 5:
        print("周末，跳过")
        return
    
    hour_min = now.hour * 100 + now.minute
    if not (925 <= hour_min <= 1135 or 1255 <= hour_min <= 1505):
        print(f"非交易时间 {now.strftime('%H:%M')}，跳过")
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
    
    # 检查每只股票
    for stock_code in stock_list.split(','):
        stock_code = stock_code.strip()
        if not stock_code:
            continue
        
        try:
            name, price = fetch_price(stock_code)
            print(f"  {name}({stock_code}): {price:.2f}")
            
            # 检查预警规则
            alerts = []
            for rule in rules:
                if rule.get('stock_code') != stock_code:
                    continue
                
                alert_type = rule.get('alert_type')
                
                if alert_type == 'price_cross':
                    target = rule.get('price', 0)
                    direction = rule.get('direction', 'above')
                    if direction == 'above' and price >= target:
                        alerts.append(f"突破 {target}")
                    elif direction == 'below' and price <= target:
                        alerts.append(f"跌破 {target}")
            
            # 发送通知
            if alerts:
                subject = f"【股价预警】{name}({stock_code})"
                content = f"当前价格: {price:.2f}\n触发: {', '.join(alerts)}\n时间: {now.strftime('%Y-%m-%d %H:%M:%S')}"
                send_email(subject, content)
            else:
                print(f"    未触发预警")
        
        except Exception as e:
            print(f"  ✗ 错误: {e}")
if __name__ == '__main__':
    main()
