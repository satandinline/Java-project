# 公共文化资源系统前端

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

## 开发说明

This template should help get you started developing with Vue 3 in Vite.

## Recommended IDE Setup

[VS Code](https://code.visualstudio.com/) + [Vue (Official)](https://marketplace.visualstudio.com/items?itemName=Vue.volar) (and disable Vetur).

## Recommended Browser Setup

- Chromium-based browsers (Chrome, Edge, Brave, etc.):
  - [Vue.js devtools](https://chromewebstore.google.com/detail/vuejs-devtools/nhdogjmejiglipccpnnnanhbledajbpd) 
  - [Turn on Custom Object Formatter in Chrome DevTools](http://bit.ly/object-formatters)
- Firefox:
  - [Vue.js devtools](https://addons.mozilla.org/en-US/firefox/addon/vue-js-devtools/)
  - [Turn on Custom Object Formatter in Firefox DevTools](https://fxdx.dev/firefox-devtools-custom-object-formatters/)

## Customize configuration

See [Vite Configuration Reference](https://vite.dev/config/).

## Project Setup

```sh
npm install
```

### Compile and Hot-Reload for Development

```sh
npm run dev
```

### Compile and Minify for Production

```sh
npm run build
```
