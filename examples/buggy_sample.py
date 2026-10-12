"""演示样例：故意包含若干典型缺陷，用于展示 Agent 的审查能力。"""
import json
import sqlite3

DB_PASSWORD = "admin123"          # 安全隐患：硬编码凭据


def get_user(username):
    conn = sqlite3.connect("app.db")
    # 安全问题：SQL 字符串拼接，存在注入风险
    cursor = conn.execute("SELECT * FROM users WHERE name = '" + username + "'")
    return cursor.fetchone()      # 缺陷：连接未关闭


def parse_config(text):
    try:
        return json.loads(text)
    except:                       # 缺陷：裸 except，吞掉 KeyboardInterrupt
        return None


def average(numbers):
    return sum(numbers) / len(numbers)   # 缺陷：空列表触发 ZeroDivisionError


def batch_predict(items, model):
    results = []
    for item in items:
        results.append(model.predict(item))   # 缺陷：无异常隔离，单条失败全批中断
    return results
