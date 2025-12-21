# 公共文化资源系统 - Java后端

这是一个基于Spring Boot的Java后端服务，使用JDBC连接MySQL数据库。

## 项目结构

```
backend/
├── src/
│   ├── main/
│   │   ├── java/com/cultural/
│   │   │   ├── config/          # 配置类（数据源、Web配置等）
│   │   │   ├── controller/      # REST API控制器
│   │   │   ├── service/         # 业务逻辑服务层
│   │   │   ├── dao/             # 数据访问对象
│   │   │   ├── entity/          # 实体类
│   │   │   ├── util/            # 工具类
│   │   │   └── CulturalResourcesApplication.java  # 主启动类
│   │   └── resources/
│   │       └── application.yml  # 配置文件
│   └── test/                    # 测试代码
└── pom.xml                      # Maven配置文件
```

## 技术栈

- **Spring Boot 3.2.0** - 应用框架
- **JDBC** - 数据库连接（替代Python的pymysql）
- **MySQL Connector/J** - MySQL驱动
- **Maven** - 项目管理和构建工具
- **Java 17** - 开发语言

## 配置说明

数据库配置在 `src/main/resources/application.yml` 中：

```yaml
spring:
  datasource:
    url: jdbc:mysql://127.0.0.1:3306/java_project?...
    username: root
    password: M17382930994c@
```

## 编译和运行

### 前置要求

1. JDK 17 或更高版本
2. Maven 3.6 或更高版本
3. MySQL 数据库已启动并创建了 `java_project` 数据库

### 编译项目

```bash
cd backend
mvn clean compile
```

### 运行项目

```bash
mvn spring-boot:run
```

或者先打包，然后运行jar文件：

```bash
mvn clean package
java -jar target/cultural-resources-backend-1.0.0.jar
```

### 开发模式运行

```bash
mvn spring-boot:run
```

服务器将在 http://localhost:8000 启动

## API端点

### 健康检查
- `GET /api/health` - 检查服务状态

### 认证相关
- `POST /api/auth/register` - 用户注册
- `POST /api/auth/login` - 用户登录
- `GET /api/auth/user` - 获取用户信息

### 资源相关
- `GET /api/home/resources` - 获取首页资源列表
  - 参数: `page` (默认1), `page_size` (默认8)

### 统计相关
- `GET /api/statistics` - 获取统计数据

## 数据库连接

本项目使用JDBC直接连接MySQL数据库，替代了原Python项目中的pymysql连接方式。

数据库配置在 `application.yml` 中，使用标准的JDBC URL格式：
```
jdbc:mysql://host:port/database?参数
```

## 开发说明

### 添加新的API端点

1. 在 `controller` 包中创建或修改控制器类
2. 在 `service` 包中实现业务逻辑
3. 在 `dao` 包中实现数据访问逻辑

### 数据库操作

使用Spring的 `JdbcTemplate` 进行数据库操作，所有DAO类都注入 `JdbcTemplate`。

## 注意事项

1. 确保MySQL数据库服务已启动
2. 确保数据库 `java_project` 已创建并包含所有必要的表
3. 确保数据库用户有足够的权限
4. 端口8000不能被其他程序占用

