# 数据库更新说明 - 超级管理员功能

## 更新内容

本次更新添加了以下功能：
1. 超级管理员角色（在原有"普通用户"和"管理员"基础上新增）
2. 用户在线状态跟踪（`is_online`字段）
3. 最后活跃时间记录（`last_active_time`字段）

## 数据库结构变更

### users表新增字段
- `is_online` TINYINT(1) DEFAULT 0 - 是否在线（0：离线，1：在线）
- `last_active_time` TIMESTAMP NULL - 最后活跃时间

### users表role字段更新
- 原值：`ENUM('普通用户', '管理员')`
- 新值：`ENUM('普通用户', '管理员', '超级管理员')`
- 默认值：`'普通用户'`

## 更新方法

### 方法一：使用Python脚本（推荐）

如果数据库已存在，直接运行更新脚本：

```bash
python database_files/run_init_schema.py
```

脚本会自动：
1. 检查并更新`role` ENUM类型（添加'超级管理员'选项）
2. 检查并添加`is_online`字段（如果不存在）
3. 检查并添加`last_active_time`字段（如果不存在）
4. 创建默认超级管理员账号（如果不存在）

### 方法二：手动执行SQL

如果只想执行更新部分，可以手动执行`init_schema.sql`文件中的以下部分：

```sql
-- 更新users表的role ENUM，添加'超级管理员'选项
-- 添加is_online字段
-- 添加last_active_time字段
```

这些SQL语句在`init_schema.sql`文件的第987-1034行。

## 默认超级管理员账号

更新完成后，系统会自动创建以下默认账号：

- **超级管理员**
  - 账号：`111111111`
  - 密码：`123456`
  - 二级问题：我的身份是？
  - 二级答案：超级管理员

- **管理员**
  - 账号：`123456789`
  - 密码：`123456`
  - 二级问题：我的身份是？
  - 二级答案：管理员

- **测试用户**
  - 账号：`987654321`
  - 密码：`123456`
  - 二级问题：我的身份是？
  - 二级答案：测试用户

**⚠️ 重要提示**：首次登录后请立即修改默认密码！

## 注意事项

1. **数据安全**：所有ALTER TABLE语句都包含条件检查，只有在字段不存在时才会添加，不会影响已有数据。

2. **兼容性**：如果数据库表结构较旧（没有新字段），脚本会自动使用兼容模式创建账号。

3. **角色限制**：`role`字段只能从以下三个值中选择：
   - `'普通用户'`（默认）
   - `'管理员'`
   - `'超级管理员'`

4. **在线状态**：用户登录时自动设置为在线（`is_online = 1`），登出时自动设置为离线（`is_online = 0`）。

## 验证更新

更新完成后，可以通过以下SQL验证：

```sql
-- 检查role ENUM是否包含超级管理员
SHOW COLUMNS FROM users WHERE Field = 'role';

-- 检查新字段是否存在
SHOW COLUMNS FROM users WHERE Field IN ('is_online', 'last_active_time');

-- 检查超级管理员账号是否存在
SELECT account, nickname, role FROM users WHERE role = '超级管理员';
```

## 问题排查

如果更新后没有超级管理员账号：

1. 检查SQL执行日志，查看是否有错误
2. 检查账号是否已存在（脚本会跳过已存在的账号）
3. 手动执行以下SQL创建超级管理员账号：

```sql
INSERT INTO users (account, password_hash, role, nickname, avatar_path, security_question, security_answer_hash, is_online)
VALUES (
    '111111111',
    '8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92',  -- 123456的SHA256哈希
    '超级管理员',
    '超级管理员',
    '/default.jpg',
    '我的身份是？',
    'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',  -- '超级管理员'的SHA256哈希
    0
);
```

