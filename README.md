# Telegram通知程序

一个用于监控日志文件中的关键词并通过Telegram Bot发送通知的程序。

## 功能特点

- 监控多个日志文件中的关键词
- 支持普通文本和正则表达式匹配
- 使用Telegram Bot API发送通知
- 支持HTML和Markdown格式消息
- 后台守护进程模式运行
- 可配置的监控间隔
- 支持多种日志格式，包括多行日志
- 支持使用通配符匹配多个日志文件
- **新功能**：支持按项目分类的多配置文件管理
- **新功能**：标准化的日志文件命名格式

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
# 或者创建项目专属的配置文件
mkdir -p keyword_config
cp config/keyword_config.yml.example keyword_config/project1_keyword.yml
```

2. 修改配置文件

- 修改 `config/telegram_config.yml` 文件，填入你的Telegram Bot Token和Chat ID
- 修改 `config/keyword_config.yml` 文件，配置需要监控的日志文件和关键词
- 或者按项目创建并配置 `keyword_config/` 目录下的多个配置文件

## 使用方法

### 命令行参数

程序支持以下命令行参数：

```
--config CONFIG    配置文件目录路径
--debug            启用调试模式
```

子命令：

- `start`：启动监控服务
  - `--no-daemon`：前台运行，不作为守护进程
  - `--interval N`：设置检查间隔（秒）
- `stop`：停止监控服务
- `test`：发送测试消息
  - `--message MSG`：指定测试消息内容
- `status`：查看服务状态

### 启动监控服务

```bash
# 前台运行（调试模式）
python tg_notification.py --debug start --no-daemon

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

### 关键词配置

程序支持两种配置关键词的方式：

#### 1. 单一配置文件 (config/keyword_config.yml)

```yaml
# 日志文件列表
log_files:
  - path: "/var/log/application.log"  # 日志文件路径
    keywords:  # 关键词列表
      - "ERROR"
      - "FATAL"
      - "Exception"
    use_regex: false  # 是否使用正则表达式匹配
    
  # 多行日志配置示例
  - path: "/var/log/multiline.log"
    keywords:
      - "ERROR"
      - "WARNING"
    # 多行日志配置
    multiline:
      type: "pattern"
      # 匹配新日志行开始的模式
      pattern: "^\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}:\\d{2}"
      
  # 通配符路径示例（监控所有.log文件）
  - path: "/home/user/logs/*.log"
    keywords:
      - "ERROR"
      - "失败"
    multiline:
      type: "pattern"
      pattern: "^\\[\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}:\\d{2}\\]"
```

#### 2. 按项目分类的多配置文件 (keyword_config/ 目录)

您可以在 `keyword_config/` 目录下创建多个 YAML 文件，每个文件对应不同的项目或应用。程序将自动读取并合并所有配置文件中的监控项。

例如，创建 `keyword_config/project1_keyword.yml`：

```yaml
# 项目1关键词监控配置
log_files:
  - path: "/var/log/project1/application.log"
    keywords:
      - "ERROR"
      - "FATAL"
    use_regex: false

log_reader:
  context_lines: 3  # 项目特定的配置
```

创建 `keyword_config/project2_keyword.yml`：

```yaml
# 项目2关键词监控配置
log_files:
  - path: "/var/log/project2/api.log"
    keywords:
      - "API调用失败"
      - "超时"
    use_regex: false
```

#### 配置文件读取顺序

程序按照以下优先顺序加载配置：

1. 首先检查项目根目录下的 `keyword_config/` 目录
2. 如果在根目录下没有找到配置文件，则检查 `config/keyword_config/` 目录
3. 如果在目录中都没有找到配置文件，则尝试读取 `config/keyword_config.yml` 单一配置文件
4. 如果所有位置都没有找到配置文件，则返回空配置（但会记录警告）

这种方式的优势：
- 按项目组织配置，更清晰易管理
- 不同团队可以独立维护各自的配置
- 易于版本控制和比较差异
- 灵活的配置文件存放位置，适应不同的部署环境

### 标准化日志文件名

程序现在使用标准化的日志文件命名格式：

```
[功能名称]_当前日期时间_级别.log
```

例如：
- `tg_notification_20250330_081502_INFO.log`
- `tg_notification_20250330_081502_ERROR.log`
- `tg_notification_20250330_081502_WARNING.log`
- `tg_notification_20250330_081502_DEBUG.log`

这种命名方式的优势：
- 通过文件名可以快速识别日志来源、时间和级别
- 不同级别的日志分离，便于排查特定类型的问题
- 时间戳便于归档和查找特定时间段的日志

### 支持的日志格式

程序支持以下几种常见的日志格式：

1. **标准日志格式**：`2025-03-28 10:15:23.456 [INFO] [main-thread] [TX123456] [PID9876] 消息内容`
2. **方括号日期格式**：`[2025-03-28 10:15:23] [system] [INFO] 消息内容`
3. **简单日志格式**：`2023-07-01 10:15:38 ERROR 消息内容`

对于多行日志（如异常堆栈），需要在配置文件中指定多行模式的正则表达式模式，程序将自动合并属于同一条日志的多行内容。

### 通配符路径

程序支持在配置文件中使用通配符路径，可以匹配多个日志文件：

- `*`：匹配任意数量的字符（不包括目录分隔符）
- `?`：匹配单个字符
- `[abc]`：匹配字符集合中的任意一个字符

例如：
- `/var/log/*.log`：匹配/var/log/目录下所有.log文件
- `/var/log/app-?.log`：匹配/var/log/目录下的app-1.log、app-2.log等文件
- `/home/*/logs/error.log`：匹配所有用户目录下的logs/error.log文件

程序会定期检查通配符路径，如果发现新文件，会自动添加到监控列表中。

## 日志文件

程序的日志文件保存在 `logs/` 目录下，文件名格式为 `[功能名称]_YYYYMMDD_HHMMSS_级别.log`。

## 圖例
<img width="437" alt="image" src="https://github.com/user-attachments/assets/61366379-5225-4a4d-aad5-eae8401a50b3" />

