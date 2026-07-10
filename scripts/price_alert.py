#!/usr/bin/env python3
"""
轻量级价格预警脚本
只做价格检查 + 邮件通知，不运行完整分析流程
"""
import os
import json
import urllib.request
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timezone, timedelta
# 配置
STOCK_LIST = os.environ.get('STOCK_LIST', '002658')
ALERT_RULES = os.environ.get('AGENT_EVENT_ALERT_RULES_JSON', '[]')
EMAIL_SENDER = os.environ.get('EMAIL_SENDER', '')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD', '')
EMAIL_RECEIVERS = os.environ.get('EMAIL_RECEIVERS', '')
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
    msg = MIMEText(content, 'plain', 'utf-8')
    msg['Subject'] = subject
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_RECEIVERS
    
    with smtplib.SMTP_SSL('smtp.qq.com', 465) as smtp:
        smtp.login(EMAIL_SENDER, EMAIL_PASSWORD)
        smtp.sendmail(EMAIL_SENDER, EMAIL_RECEIVERS.split(','), msg.as_string())
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
    
    # 解析预警规则
    rules = json.loads(ALERT_RULES)
    
    # 检查每只股票
    for stock_code in STOCK_LIST.split(','):
        stock_code = stock_code.strip()
        try:
            name, price = fetch_price(stock_code)
            print(f"{name}({stock_code}): {price:.2f}")
            
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
                
                elif alert_type == 'price_change_percent':
                    # 需要昨收价，这里简化处理
                    pass
                
                elif alert_type == 'volume_spike':
                    # 成交量检查需要历史数据，这里简化
                    pass
            
            # 发送通知
            if alerts:
                subject = f"【股价预警】{name}({stock_code})"
                content = f"当前价格: {price:.2f}\n触发: {', '.join(alerts)}\n时间: {now.strftime('%Y-%m-%d %H:%M:%S')}"
                print(f"  → 发送通知: {alerts}")
                send_email(subject, content)
        
        except Exception as e:
            print(f"  ✗ 错误: {e}")
if __name__ == '__main__':
    main()
