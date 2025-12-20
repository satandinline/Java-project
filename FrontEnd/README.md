# 公共文化资源系统前端

基于 Vue.js 3 + Vite + Vue Router 4 构建的前端应用。

## 快速启动

### 前置准备

**首次使用需要安装依赖：**

在项目根目录运行：
```bash
# Windows
python install_dependencies.py

# Linux/Mac
python3 install_dependencies.py
```

这会自动安装所有Python和Node.js依赖。

### 方式一：使用启动脚本（推荐，一键启动前后端）

**Windows系统：**
```bash
# 在项目根目录运行
start_dev.bat
```

**Linux/Mac系统：**
```bash
# 在项目根目录运行
chmod +x start_dev.sh
./start_dev.sh
```

### 方式二：使用npm命令（在FrontEnd目录）

```bash
cd FrontEnd
npm install  # 如果还没安装依赖
npm run dev:full
```

这会同时启动：
- 前端开发服务器：http://localhost:5173
- 后端API服务器：http://localhost:8000（内部服务，通过前端代理访问）

### 方式三：分别启动

**只启动前端：**
```bash
cd FrontEnd
npm run dev
```

**只启动后端：**
```bash
# 在项目根目录运行
python AIGC/aigc_api_server.py
```

## 项目结构

```
FrontEnd/
├── public/              # 静态资源目录
│   ├── default.jpg     # 默认头像（必须存在）
│   ├── favicon.ico     # 网站图标
│   ├── images/         # 图片资源
│   └── videos/         # 视频资源
├── src/
│   ├── assets/         # 样式和静态资源
│   ├── components/     # Vue组件
│   │   ├── Login.vue          # 登录/注册组件
│   │   ├── HomeView.vue       # 首页组件
│   │   ├── AIGCView.vue       # AIGC功能页面
│   │   ├── MultiModalSearch.vue # 图文互搜页面
│   │   ├── ResourceUpload.vue  # 资源上传页面
│   │   └── AnnotationTasks.vue # 标注任务页面
│   ├── router/         # 路由配置
│   │   └── index.js    # 路由定义和导航守卫
│   ├── App.vue         # 根组件
│   └── main.js         # 应用入口
├── index.html          # HTML模板
├── vite.config.js      # Vite配置
└── package.json        # 依赖配置
```

## 功能模块

### 1. 用户认证
- **注册**：系统自动生成8-10位数字账号，支持密码、昵称、头像上传、安全问题设置
- **登录**：使用账号（8-10位数字）和密码登录
- **忘记密码**：通过自定义安全问题找回密码
- **用户设置**（列表式布局，类似QQ设置）：
  - **账号**：仅显示，不可修改（显示8-10位数字账号）
  - **昵称**：可点击修改，下方显示当前昵称
  - **个人签名**：可点击设置，下方显示当前签名（最多500字符，未设置时显示"未设置"）
  - **修改密码**：可点击进入密码修改界面（支持原密码或二级密码验证）
  - **更换二级问题**：可点击进入安全问题设置界面
  - **退出登录**：红色文字，点击后退出登录
  - **注销账号**：红色文字，位于最底部，需要输入密码确认，注销后账号永久删除
- **更换头像**：
  - 方式一：点击右上角"设置"按钮，在设置列表中点击"更换头像"
  - 方式二：直接点击页面右上角的用户头像，直接进入头像更换界面
- **用户资料**：显示用户昵称和头像（头像下方只显示昵称，不显示账号）

### 2. 首页
- 3D轮播视频展示
- 文化资源卡片展示（分页）
- 资源详情查看

### 3. AIGC功能
- **文字AIGC（Tongyi模型）**：
  - 智能问答，支持RAG检索
  - 支持上传图片并理解图片内容
  - 无文字提示时自动生成传统文化故事
  - 生成内容具有高辨识度
- **图片AIGC（Huoshan模型）**：
  - 图像生成，支持参考图片输入
  - 支持上传图片并理解图片内容
  - 无文字提示时自动生成故事并生成连环画
  - 生成的图片以假乱真
- **会话管理**：
  - 自动保存对话历史（用户输入和AI回答分别存储）
  - 支持新建会话
  - 支持加载历史会话
  - 支持删除会话（单个、批量、全部）
  - 支持隐藏/显示历史记录面板
  - 显示模型名称（Tongyi/Huoshan）

### 4. 图文互搜
- 图片和文本的相互检索

### 5. 资源上传
- 用户上传文本或图片资源
- 上传进度显示

### 6. 标注任务
- 查看标注任务列表
- 用户只能看到自己上传资源的标注任务
- 管理员可以看到所有资源的标注任务

## 路由配置

- `/login` - 登录/注册页面
- `/` - 首页
- `/aigc` - AIGC功能页面
- `/multimodal` - 图文互搜页面
- `/upload` - 资源上传页面
- `/annotation` - 标注任务页面

## 路由守卫

- 未登录用户访问受保护路由时自动跳转到登录页
- 已登录用户访问登录页时自动跳转到首页

## 静态资源

### 默认头像
- 位置：`public/default.jpg`
- 用途：用户未上传头像时显示
- 访问路径：`/default.jpg`

### 用户头像
- 存储位置：项目根目录的 `public/` 文件夹（与 `start_dev.bat` 同目录）
- 命名格式：`{account}.jpg`（如：123456789.jpg，使用账号而非用户名）
- 默认头像：`default.jpg`（默认管理员和测试用户都使用此头像）
- 访问路径：`/{account}.jpg` 或 `/default.jpg`
- 通过Flask静态文件服务提供

## 开发说明

### 技术栈
- **框架**：Vue.js 3 (Composition API)
- **构建工具**：Vite
- **路由**：Vue Router 4
- **状态管理**：Vue 3 Composition API (ref, computed)

### 开发工具推荐

**IDE：**
- [VS Code](https://code.visualstudio.com/) + [Vue (Official)](https://marketplace.visualstudio.com/items?itemName=Vue.volar)

**浏览器扩展：**
- [Vue.js devtools](https://chromewebstore.google.com/detail/vuejs-devtools/nhdogjmejiglipccpnnnanhbledajbpd)

### 开发命令

```sh
# 安装依赖
npm install

# 启动开发服务器（仅前端）
npm run dev

# 启动开发服务器（前后端同时启动）
npm run dev:full

# 构建生产版本
npm run build

# 预览生产构建
npm run preview
```

### 代码规范

- 使用 Composition API
- 组件使用 `<script setup>` 语法
- 使用 TypeScript 类型提示（可选）

## 常见问题

### 1. 页面空白
- 检查浏览器控制台错误
- 确认后端API服务器运行正常
- 检查路由配置是否正确

### 2. 图片无法显示
- 确认 `public/default.jpg` 文件存在
- 检查图片路径是否正确
- 验证Vite代理配置

### 3. 路由跳转失败
- 检查 `router/index.js` 配置
- 确认组件导入路径正确
- 查看浏览器控制台错误信息

### 4. 显示已删除的用户信息
- **问题**：即使数据库已删除用户，浏览器仍可能显示旧的用户信息（如昵称"立线"）
- **原因**：用户信息存储在浏览器的localStorage中
- **解决方法**：
  1. 打开浏览器开发者工具（F12）
  2. 进入"应用程序"（Application）或"存储"（Storage）标签
  3. 找到"本地存储"（Local Storage）中的 `userInfo` 项
  4. 删除该项或清除所有本地存储
  5. 刷新页面，系统会自动清除无效的用户信息
- **注意**：系统已添加自动验证机制，如果localStorage中的用户信息无效，会自动清除

## 配置说明

### Vite代理配置

在 `vite.config.js` 中配置了以下代理：
- `/api/*` → `http://localhost:8000` (后端API)

### 环境变量

前端通过Vite代理访问后端，无需单独配置环境变量。

## 许可证

本项目遵循项目主许可证。
