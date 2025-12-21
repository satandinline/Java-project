# 后端迁移指南：Python到Java

本文档说明如何将后端从Python Flask迁移到Java Spring Boot，并使用JDBC连接数据库。

## 迁移概述

### 已完成的工作

1. ✅ 创建了Java Spring Boot项目结构
2. ✅ 配置了JDBC数据库连接（替代pymysql）
3. ✅ 迁移了认证系统（注册、登录）
4. ✅ 迁移了统计API
5. ✅ 迁移了首页资源列表API
6. ✅ 创建了文件上传控制器（基础版本）

### 项目结构

```
backend/
├── src/main/java/com/cultural/
│   ├── config/              # 配置类
│   │   ├── DataSourceConfig.java    # JDBC数据源配置
│   │   └── WebConfig.java           # Web配置（CORS、静态资源）
│   ├── controller/          # REST API控制器
│   │   ├── AuthController.java      # 认证API
│   │   ├── HealthController.java    # 健康检查
│   │   ├── ResourceController.java  # 资源API
│   │   ├── StatisticsController.java # 统计API
│   │   └── UploadController.java    # 上传API
│   ├── service/             # 业务逻辑层
│   │   ├── AuthService.java
│   │   ├── ResourceService.java
│   │   └── StatisticsService.java
│   ├── dao/                 # 数据访问层
│   │   ├── UserDao.java
│   │   └── CulturalResourceDao.java
│   ├── entity/              # 实体类
│   │   ├── User.java
│   │   └── CulturalResource.java
│   ├── util/                # 工具类
│   │   ├── PasswordUtil.java
│   │   └── AccountUtil.java
│   └── CulturalResourcesApplication.java  # 主启动类
├── src/main/resources/
│   └── application.yml      # 配置文件
└── pom.xml                  # Maven配置
```

## 数据库连接对比

### Python (原实现)
```python
# db_connection.py
import pymysql
conn = pymysql.connect(
    host="127.0.0.1",
    port=3306,
    user="root",
    password="password",
    database="java_project",
    charset="utf8mb4",
    cursorclass=DictCursor
)
```

### Java (新实现)
```java
// DataSourceConfig.java
@Configuration
public class DataSourceConfig {
    @Bean
    public DataSource dataSource() {
        DriverManagerDataSource dataSource = new DriverManagerDataSource();
        dataSource.setDriverClassName("com.mysql.cj.jdbc.Driver");
        dataSource.setUrl("jdbc:mysql://127.0.0.1:3306/java_project?...");
        dataSource.setUsername("root");
        dataSource.setPassword("password");
        return dataSource;
    }
}
```

### 配置文件
```yaml
# application.yml
spring:
  datasource:
    driver-class-name: com.mysql.cj.jdbc.Driver
    url: jdbc:mysql://127.0.0.1:3306/java_project?useUnicode=true&characterEncoding=utf8mb4&useSSL=false&serverTimezone=Asia/Shanghai
    username: root
    password: M17382930994c@
```

## 运行方式

### 启动Java后端

**Windows:**
```bash
cd backend
start_backend.bat
```

**Linux/Mac:**
```bash
cd backend
chmod +x start_backend.sh
./start_backend.sh
```

**或者使用Maven命令:**
```bash
cd backend
mvn spring-boot:run
```

### 前端配置

前端已经配置了代理，无需修改。`FrontEnd/vite.config.js` 中的配置会代理 `/api` 请求到 `http://localhost:8000`。

## 待完成的工作

以下功能需要继续实现：

1. **资源上传功能完整实现**
   - 文件保存
   - 数据库记录
   - 标注任务创建
   - AI标注触发

2. **AIGC相关API**
   - 文字AIGC聊天接口
   - 图片AIGC生成接口
   - 会话管理

3. **搜索功能**
   - 全文搜索
   - AI辅助搜索

4. **标注任务管理**
   - 任务列表
   - 任务详情
   - 审核功能

5. **评论系统**
   - 评论列表
   - 评论创建
   - 点赞功能

6. **其他API端点**
   - 资源详情
   - 用户信息更新
   - 密码修改
   - 安全问题相关

## API端点对照表

| 功能 | Python路径 | Java路径 | 状态 |
|------|-----------|----------|------|
| 健康检查 | GET /api/health | GET /api/health | ✅ |
| 用户注册 | POST /api/auth/register | POST /api/auth/register | ✅ |
| 用户登录 | POST /api/auth/login | POST /api/auth/login | ✅ |
| 获取用户信息 | GET /api/auth/user | GET /api/auth/user | ✅ |
| 首页资源列表 | GET /api/home/resources | GET /api/home/resources | ✅ |
| 统计数据 | GET /api/statistics | GET /api/statistics | ✅ |
| 文件上传 | POST /api/upload | POST /api/upload | ⚠️ 基础版本 |
| 资源详情 | GET /api/resource/detail | - | ❌ |
| AIGC聊天 | POST /api/aigc/chat | - | ❌ |
| 搜索 | GET /api/search | - | ❌ |

## 注意事项

1. **数据库连接**
   - 确保MySQL服务已启动
   - 确保数据库 `java_project` 已创建
   - 确保数据库用户有足够权限

2. **端口冲突**
   - Java后端默认使用8000端口
   - 如果Python后端还在运行，需要先停止

3. **文件路径**
   - 上传文件路径配置在 `application.yml` 中
   - 确保目录存在或有创建权限

4. **依赖管理**
   - 首次运行需要下载Maven依赖
   - 可能需要配置Maven镜像以加快下载速度

## 扩展建议

1. **使用Spring Data JPA**
   - 当前使用JdbcTemplate，可以升级到JPA以提高开发效率

2. **添加事务管理**
   - 在Service层添加 `@Transactional` 注解

3. **异常处理**
   - 添加全局异常处理器

4. **日志系统**
   - 配置更详细的日志记录

5. **单元测试**
   - 添加Service层和DAO层的单元测试

6. **API文档**
   - 集成Swagger/OpenAPI生成API文档

