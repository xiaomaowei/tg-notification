# Telegram通知程序

一个用于监控日志文件中的关键词并通过Telegram Bot发送通知的程序。

## 功能特点

- 监控多个日志文件中的关键词
- 支持普通文本和正则表达式匹配
- 使用Telegram Bot API发送通知
- 支持HTML和Markdown格式消息
- 后台守护进程模式运行
- 可配置的监控间隔

## 安装

### 安装依赖

```bash
pip install -r requirements.txt
```

### 配置

1. 复制配置文件示例

```bash
cp config/telegram_config.yml.example config/telegram_config.yml
cp config/keyword_config.yml.example config/keyword_config.yml
```

2. 修改配置文件

- 修改 `config/telegram_config.yml` 文件，填入你的Telegram Bot Token和Chat ID
- 修改 `config/keyword_config.yml` 文件，配置需要监控的日志文件和关键词

## 使用方法

### 启动监控服务

```bash
# 前台运行（调试模式）
python tg_notification.py start --no-daemon --debug

# 后台运行
python tg_notification.py start

# 指定检查间隔（秒）
python tg_notification.py start --interval 30
```

### 停止监控服务

```bash
python tg_notification.py stop
```

### 查看服务状态

```bash
python tg_notification.py status
```

### 发送测试消息

```bash
python tg_notification.py test
python tg_notification.py test --message "自定义测试消息"
```

## 配置说明

### Telegram配置 (telegram_config.yml)

```yaml
# Bot Token，从BotFather获取
bot_token: "YOUR_BOT_TOKEN_HERE"

# Chat ID，接收消息的目标ID
chat_id: "YOUR_CHAT_ID_HERE"

# 消息解析模式，支持HTML、Markdown或留空（纯文本）
parse_mode: "HTML"
```

### 关键词配置 (keyword_config.yml)

```yaml
# 日志文件列表
log_files:
  - path: "/var/log/application.log"  # 日志文件路径
    keywords:  # 关键词列表
      - "ERROR"
      - "FATAL"
      - "Exception"
    use_regex: false  # 是否使用正则表达式匹配
```

## 日志文件

程序的日志文件保存在 `logs/tg_notification.log`，可用于调试和查看运行情况。
