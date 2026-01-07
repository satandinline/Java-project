# Cultural Resources Backend (Java Spring Boot)

这是公共文化资源系统的 Java Spring Boot 后端实现，与现有的 Python 后端并行存在。

## 项目结构

```
backend-java/
├── pom.xml                          # Maven 配置文件
├── README.md                        # 本文件
└── src/
    └── main/
        ├── java/
        │   └── com/
        │       └── app/
        │           ├── CulturalResourcesApplication.java  # 主应用类
        │           ├── config/                            # 配置类
        │           │   └── WebConfig.java
        │           ├── controller/                        # REST 控制器
        │           │   ├── AuthController.java
        │           │   ├── CommentController.java
        │           │   ├── StatisticsController.java
        │           │   ├── UploadController.java
        │           │   ├── ResourceController.java
        │           │   ├── SearchController.java
        │           │   └── AnnotationTaskController.java
        │           ├── entity/                            # JPA 实体类
        │           │   ├── User.java
        │           │   ├── CulturalResource.java
        │           │   ├── CulturalResourceFromUser.java
        │           │   ├── UserComment.java
        │           │   ├── CommentReply.java
        │           │   ├── AnnotationTask.java
        │           │   └── UserBehaviorLog.java
        │           ├── repository/                        # JPA Repository
        │           │   ├── UserRepository.java
        │           │   ├── CulturalResourceRepository.java
        │           │   ├── CulturalResourceFromUserRepository.java
        │           │   ├── UserCommentRepository.java
        │           │   ├── CommentReplyRepository.java
        │           │   ├── AnnotationTaskRepository.java
        │           │   └── UserBehaviorLogRepository.java
        │           ├── service/                           # 业务逻辑层
        │           │   ├── AuthService.java
        │           │   ├── CommentService.java
        │           │   ├── StatisticsService.java
        │           │   ├── AnnotationTaskService.java
        │           │   └── UserLoggingService.java
        │           └── util/                              # 工具类
        │               └── PasswordUtil.java
        └── resources/
            └── application.yml                           # 应用配置文件
```

## 功能模块

### 1. 用户认证和管理 (AuthController, AuthService)
- 用户注册
- 用户登录
- 修改密码
- 修改昵称
- 修改个人签名
- 更换头像
- 安全问题管理
- 密码重置

### 2. 资源管理 (UploadController, ResourceController)
- 资源上传（文本/图像）
- 资源查询
- 首页资源列表（每页8条）
- 资源详情

### 3. 检索功能 (SearchController, ResourceController)
- 全文检索（`/api/search`）- 每页8条数据
- AI检索（`/api/ai_search`）- 每页8条数据

### 4. 评论系统 (CommentController, CommentService)
- 获取评论列表
- 创建评论
- 回复评论
- 点赞功能

### 5. 标注任务管理 (AnnotationTaskController, AnnotationTaskService)
- 获取标注任务列表（每页12条数据）
- 支持状态过滤
- 支持管理员/普通用户权限控制

### 6. 统计API (StatisticsController, StatisticsService)
- 访问人次统计
- AIGC 使用量统计
- 趋势数据

### 7. 用户日志 (UserLoggingService)
- 用户行为日志记录
- 登录、注册、上传、搜索等行为记录

## 分页配置

- **检索结果**：每页 **8条** 数据（`/api/search`, `/api/ai_search`, `/api/home/resources`）
- **标注任务**：每页 **12条** 数据（`/api/annotation/tasks`）

## 数据库配置

在 `application.yml` 中配置数据库连接：

```yaml
spring:
  datasource:
    url: jdbc:mysql://127.0.0.1:3306/java_project?useUnicode=true&characterEncoding=utf8mb4&useSSL=false&serverTimezone=Asia/Shanghai
    username: root
    password: M17382930994c@
```

## 运行说明

1. 确保已安装 Java 17 和 Maven
2. 配置数据库连接（修改 `application.yml`）
3. 运行：
   ```bash
   mvn spring-boot:run
   ```
4. 服务将在 `http://localhost:7201` 启动

## 注意事项

- 本 Java 后端与 Python 后端并行存在，互不影响
- 前端仍使用 Python 后端，Java 后端处于"待切换"状态
- 部分功能（如文件上传、标注任务详情等）需要进一步完善实现
- RAG/AIGC 相关功能保留在 Python 后端，未迁移到 Java
- **Python 后端的运行时警告（USER_AGENT、LangChain废弃警告）不影响功能，如需修复需要在Python后端进行**

## API 接口

所有接口路径与 Python 版本保持一致，例如：
- `POST /api/auth/register` - 用户注册
- `POST /api/auth/login` - 用户登录
- `GET /api/comments?resource_id=xxx` - 获取评论
- `POST /api/comments` - 创建评论
- `GET /api/statistics?userId=xxx` - 获取统计数据
- `GET /api/search?q=xxx&page=1&page_size=8` - 全文检索（每页8条）
- `GET /api/annotation/tasks?user_id=xxx&page=1&page_size=12` - 获取标注任务（每页12条）
