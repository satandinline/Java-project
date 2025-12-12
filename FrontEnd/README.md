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
- 后端API服务器：http://localhost:5000

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
- **登录/注册**：支持用户名、密码、昵称、头像上传
- **忘记密码**：通过自定义安全问题找回密码
- **修改密码**：登录后可在设置中修改密码
- **用户资料**：显示用户昵称和头像

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
- 后端存储位置：`avatars/` 目录
- 前端访问路径：`/avatars/{filename}`
- 通过Vite代理转发到后端服务器

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
- `/api/*` → `http://localhost:5000` (后端API)
- `/avatars/*` → `http://localhost:5000` (用户头像)
- `/default.jpg` → `http://localhost:5000` (默认头像)

### 环境变量

前端通过Vite代理访问后端，无需单独配置环境变量。

## 许可证

本项目遵循项目主许可证。
