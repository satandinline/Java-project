# DataEase 数据监控集成文档

## 概述

本文档说明如何将公共文化资源管理系统与 DataEase 开源数据可视化平台集成，实现数据监控和统计展示。

## 前置条件

1. **DataEase 安装**
   - 下载地址：https://github.com/dataease/dataease
   - 支持 Docker 部署和本地部署
   - 推荐使用 Docker 部署（最简单）

2. **系统要求**
   - 已部署并运行公共文化资源管理系统
   - 后端API服务器正常运行（默认端口8000）
   - 数据库连接正常

## 一、DataEase 安装部署

### 方式一：Docker 部署（推荐）

```bash
# 1. 拉取 DataEase 镜像
docker pull dataease/dataease:latest

# 2. 创建数据目录
mkdir -p /opt/dataease/data
mkdir -p /opt/dataease/logs

# 3. 运行 DataEase 容器
docker run -d \
  --name dataease \
  -p 8081:8081 \
  -v /opt/dataease/data:/opt/dataease/data \
  -v /opt/dataease/logs:/opt/dataease/logs \
  dataease/dataease:latest
```

### 方式二：本地部署

参考 DataEase 官方文档：https://dataease.io/docs/

## 二、配置数据源

### 1. 登录 DataEase

- 访问地址：http://localhost:8081
- 默认账号：admin
- 默认密码：DataEase@123456

### 2. 添加 MySQL 数据源

1. 进入 **数据源** → **添加数据源**
2. 选择 **MySQL**
3. 填写连接信息：
   - **数据源名称**：公共文化资源系统
   - **主机**：127.0.0.1（或数据库服务器IP）
   - **端口**：3306
   - **数据库**：java_project
   - **用户名**：root（或数据库用户名）
   - **密码**：数据库密码
4. 点击 **测试连接**，确认连接成功
5. 点击 **保存**

## 三、使用 API 数据源（推荐方式）

### 1. 添加 API 数据源

1. 进入 **数据源** → **添加数据源**
2. 选择 **API**
3. 填写连接信息：
   - **数据源名称**：公共文化资源系统统计API
   - **请求地址**：http://localhost:8000/api/statistics
   - **请求方式**：GET
   - **请求头**（可选）：
     ```
     Content-Type: application/json
     ```
4. 点击 **测试连接**，确认连接成功
5. 点击 **保存**

### 2. API 接口说明

#### 基础统计接口

**接口地址**：`GET /api/statistics`

**返回格式**：
```json
{
  "success": true,
  "data": {
    "total_visits": 100,           // 历史访问人次
    "today_visits": 10,             // 今日访问人次
    "total_uploads": 50,            // 历史用户上传内容数量
    "today_uploads": 5,             // 今日用户上传数量
    "total_aigc": 200,              // 历史AIGC使用总量
    "today_aigc": 20,               // 今日AIGC使用总量
    "total_text_aigc": 150,         // 历史文字AIGC使用量
    "today_text_aigc": 15,          // 今日文字AIGC使用量
    "total_image_aigc": 50,         // 历史图片AIGC使用量
    "today_image_aigc": 5,          // 今日图片AIGC使用量
    "current_date": "2024-01-15"    // 当前日期
  }
}
```

#### 详细统计接口（时间序列）

**接口地址**：`GET /api/statistics/detailed?days=7`

**查询参数**：
- `days`：返回最近N天的数据（默认7天）

**返回格式**：
```json
{
  "success": true,
  "data": {
    "daily_visits": {
      "2024-01-15": 10,
      "2024-01-14": 8,
      ...
    },
    "daily_uploads": {
      "2024-01-15": 5,
      "2024-01-14": 3,
      ...
    },
    "daily_aigc": {
      "2024-01-15": {
        "total": 20,
        "text": 15,
        "image": 5
      },
      ...
    },
    "days": 7
  }
}
```

## 四、创建数据监控仪表板

### 1. 创建数据集

#### 方式一：使用 API 数据源（推荐）

1. 进入 **数据集** → **添加数据集**
2. 选择 **API数据源** → **公共文化资源系统统计API**
3. 数据集名称：系统统计数据
4. 选择返回的字段：
   - total_visits（历史访问人次）
   - today_visits（今日访问人次）
   - total_uploads（历史用户上传内容数量）
   - today_uploads（今日用户上传数量）
   - total_aigc（历史AIGC使用总量）
   - today_aigc（今日AIGC使用总量）
   - total_text_aigc（历史文字AIGC使用量）
   - today_text_aigc（今日文字AIGC使用量）
   - total_image_aigc（历史图片AIGC使用量）
   - today_image_aigc（今日图片AIGC使用量）

#### 方式二：使用 MySQL 数据源（直接查询数据库）

1. 进入 **数据集** → **添加数据集**
2. 选择 **MySQL数据源** → **公共文化资源系统**
3. 使用 SQL 查询：

```sql
-- 历史访问人次
SELECT COUNT(DISTINCT user_id) as total_visits
FROM user_behavior_logs
WHERE behavior_type = '交互' AND content LIKE '用户登录%';

-- 今日访问人次
SELECT COUNT(DISTINCT user_id) as today_visits
FROM user_behavior_logs
WHERE behavior_type = '交互' 
  AND content LIKE '用户登录%'
  AND DATE(timestamp) = CURDATE();

-- 历史用户上传内容数量
SELECT COUNT(*) as total_uploads
FROM cultural_resources_from_user;

-- 今日用户上传数量
SELECT COUNT(*) as today_uploads
FROM cultural_resources_from_user
WHERE DATE(upload_time) = CURDATE();

-- 历史AIGC使用总量
SELECT COUNT(*) as total_aigc
FROM qa_messages
WHERE model IN ('text', 'image');

-- 今日AIGC使用总量
SELECT COUNT(*) as today_aigc
FROM qa_messages
WHERE model IN ('text', 'image')
  AND DATE(create_time) = CURDATE();

-- 历史文字AIGC使用量
SELECT COUNT(*) as total_text_aigc
FROM qa_messages
WHERE model = 'text';

-- 今日文字AIGC使用量
SELECT COUNT(*) as today_text_aigc
FROM qa_messages
WHERE model = 'text'
  AND DATE(create_time) = CURDATE();

-- 历史图片AIGC使用量
SELECT COUNT(*) as total_image_aigc
FROM qa_messages
WHERE model = 'image';

-- 今日图片AIGC使用量
SELECT COUNT(*) as today_image_aigc
FROM qa_messages
WHERE model = 'image'
  AND DATE(create_time) = CURDATE();
```

### 2. 创建仪表板

1. 进入 **仪表板** → **新建仪表板**
2. 仪表板名称：公共文化资源系统监控
3. 添加图表组件：

#### 指标卡组件

**历史访问人次**
- 数据源：系统统计数据
- 字段：total_visits
- 显示格式：数字

**今日访问人次**
- 数据源：系统统计数据
- 字段：today_visits
- 显示格式：数字

**历史用户上传内容数量**
- 数据源：系统统计数据
- 字段：total_uploads
- 显示格式：数字

**今日用户上传数量**
- 数据源：系统统计数据
- 字段：today_uploads
- 显示格式：数字

**历史AIGC使用总量**
- 数据源：系统统计数据
- 字段：total_aigc
- 显示格式：数字

**今日AIGC使用总量**
- 数据源：系统统计数据
- 字段：today_aigc
- 显示格式：数字

**历史文字AIGC使用量**
- 数据源：系统统计数据
- 字段：total_text_aigc
- 显示格式：数字

**今日文字AIGC使用量**
- 数据源：系统统计数据
- 字段：today_text_aigc
- 显示格式：数字

**历史图片AIGC使用量**
- 数据源：系统统计数据
- 字段：total_image_aigc
- 显示格式：数字

**今日图片AIGC使用量**
- 数据源：系统统计数据
- 字段：today_image_aigc
- 显示格式：数字

#### 图表组件（可选）

**AIGC使用趋势图**
- 使用详细统计接口（/api/statistics/detailed）
- X轴：日期
- Y轴：使用量
- 系列：文字AIGC、图片AIGC

**访问人次趋势图**
- 使用详细统计接口
- X轴：日期
- Y轴：访问人次

**上传数量趋势图**
- 使用详细统计接口
- X轴：日期
- Y轴：上传数量

### 3. 设置自动刷新

1. 进入仪表板编辑模式
2. 点击 **设置** → **自动刷新**
3. 设置刷新间隔（建议：5分钟或10分钟）
4. 保存设置

## 五、用户行为日志实时记录

系统已实现用户行为日志的实时记录功能，所有关键操作都会自动记录到 `user_behavior_logs` 表中：

### 已记录的日志类型

1. **用户登录**：每次用户登录时记录
2. **用户注册**：每次用户注册时记录
3. **资源上传**：每次用户上传资源时记录
4. **AIGC使用**：
   - 文字AIGC：每次使用文字AIGC时记录
   - 图片AIGC：每次使用图片AIGC时记录
5. **搜索行为**：每次执行搜索时记录
6. **标注行为**：每次进行标注操作时记录

### 日志记录位置

- **登录/注册**：`AIGC/aigc_api_server.py` 的登录和注册接口
- **资源上传**：`upload_handler.py` 的上传方法
- **AIGC使用**：`AIGC/aigc_api_server.py` 的AIGC聊天接口
- **搜索行为**：搜索相关接口（需要添加）

### 日志工具类

系统提供了统一的日志记录工具类 `user_logging.py`，包含以下方法：

- `log_behavior()`: 通用日志记录方法
- `log_login()`: 记录登录
- `log_register()`: 记录注册
- `log_aigc_text()`: 记录文字AIGC使用
- `log_aigc_image()`: 记录图片AIGC使用
- `log_upload()`: 记录资源上传
- `log_search()`: 记录搜索行为
- `log_annotation()`: 记录标注行为

## 六、注意事项

1. **日期匹配逻辑**
   - 所有"今日"统计都使用 `DATE()` 函数匹配当前日期
   - 确保数据库服务器时区设置正确
   - 建议使用 UTC 时间或统一时区

2. **性能优化**
   - 统计API已添加必要的数据库索引
   - 建议定期清理历史日志数据（保留最近3-6个月）
   - 对于大量数据，考虑使用缓存机制

3. **数据准确性**
   - 确保所有关键操作都已添加日志记录
   - 定期检查日志记录的完整性
   - 监控日志记录失败的情况

4. **安全考虑**
   - 统计API接口建议添加管理员权限验证
   - 限制API访问频率，防止恶意请求
   - 敏感数据不要记录在日志中

## 七、故障排除

### 问题1：API接口返回错误

**解决方案**：
1. 检查后端服务是否正常运行
2. 检查数据库连接是否正常
3. 查看后端日志文件

### 问题2：统计数据不准确

**解决方案**：
1. 检查日志记录是否正常
2. 确认日期匹配逻辑正确
3. 检查数据库时区设置

### 问题3：DataEase 无法连接数据源

**解决方案**：
1. 检查网络连接
2. 确认防火墙设置
3. 验证数据库/API访问权限

## 八、扩展功能

### 1. 添加更多统计维度

可以在 `statistics_api.py` 中添加更多统计接口，例如：
- 用户活跃度统计
- 资源类型分布统计
- 标注任务完成率统计
- 用户评分统计

### 2. 实时监控告警

可以集成告警功能，当某些指标超过阈值时发送通知。

### 3. 数据导出

可以在 DataEase 中配置数据导出功能，定期导出统计数据。

## 九、相关文件

- `user_logging.py`：用户行为日志记录工具
- `statistics_api.py`：统计数据API接口
- `AIGC/aigc_api_server.py`：主API服务器（已集成日志记录）
- `upload_handler.py`：资源上传处理（已集成日志记录）

## 十、技术支持

如有问题，请参考：
- DataEase 官方文档：https://dataease.io/docs/
- 项目技术实现手册：`技术实现手册.txt`
- 数据库说明文档：`database_files/readme.md`

