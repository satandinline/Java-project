<template>
  <div id="app">
    <!-- 顶部导航栏 -->
    <header class="main-header" v-if="isLoggedIn">
      <div class="header-content">
        <!-- 1. 修改 Logo 文字 -->
        <div class="brand">
          <span class="logo-text">公共文化资源系统</span>
        </div>

        <!-- 中间 导航链接 (包含下拉菜单) -->
        <nav class="nav-menu">
          <!-- 首页按钮 -->
          <div class="nav-item" :class="{ active: activeView === 'home' }" @click="activeView = 'home'">
            首页
          </div>

          <!-- 2. 下拉菜单组件 -->
          <div class="nav-item dropdown-trigger">
            节日名称 <span class="arrow">∨</span>
            <!-- 下拉菜单内容 -->
            <div class="dropdown-menu">
              <div class="dropdown-option">选项一</div>
              <div class="dropdown-option">选项二</div>
            </div>
          </div>

          <div class="nav-item dropdown-trigger">
            你好 <span class="arrow">∨</span>
            <div class="dropdown-menu">
              <div class="dropdown-option">选项一</div>
            </div>
          </div>

          <div class="nav-item dropdown-trigger">
            hello <span class="arrow">∨</span>
            <div class="dropdown-menu">
              <div class="dropdown-option">选项一</div>
            </div>
          </div>

          <div class="nav-item dropdown-trigger">
            节日名称 <span class="arrow">∨</span>
            <div class="dropdown-menu">
              <div class="dropdown-option">选项一</div>
            </div>
          </div>
        </nav>

        <!-- 右侧 功能区 -->
        <div class="right-actions">
          <a href="#" class="text-link" @click.prevent="activeView = 'aigc'" style="font-weight: 600; color: #409eff;">AIGC</a>
          <a href="#" class="text-link" @click.prevent="activeView = 'upload'">用户上传</a>
          <a href="#" class="text-link" @click.prevent="activeView = 'annotation'">标注任务</a>
          <button class="login-btn-pill" @click="handleAuthAction">
            退出登录
          </button>
        </div>
      </div>
    </header>
    
    <main>
      <component 
        :is="currentComponent" 
        @login-success="handleLoginSuccess"
      ></component>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import ResourceUpload from './components/ResourceUpload.vue';
import AnnotationTasks from './components/AnnotationTasks.vue';
import Login from './components/Login.vue';
import HomeView from './components/HomeView.vue';
import AIGCView from './components/AIGCView.vue';

const activeView = ref('login');
const userInfo = ref(null);

onMounted(() => {
  const savedUser = localStorage.getItem('userInfo');
  if (savedUser) {
    userInfo.value = JSON.parse(savedUser);
    activeView.value = 'home';
  }
});

const isLoggedIn = computed(() => !!userInfo.value);

const currentComponent = computed(() => {
  if (!isLoggedIn.value) return Login;
  switch (activeView.value) {
    case 'home': return HomeView;
    case 'upload': return ResourceUpload;
    case 'annotation': return AnnotationTasks;
    case 'aigc': return AIGCView;
    default: return HomeView;
  }
});

const handleLoginSuccess = (userData) => {
  userInfo.value = userData;
  localStorage.setItem('userInfo', JSON.stringify(userData));
  activeView.value = 'home';
};

const handleAuthAction = () => {
  userInfo.value = null;
  localStorage.removeItem('userInfo');
  activeView.value = 'login';
};
</script>

<style>
/* 全局重置 */
body { margin: 0; font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif; background-color: #fcfcfc; }

.main-header {
  border-bottom: 1px solid #eee;
  background: white;
  padding: 0 20px;
  box-shadow: 0 2px 6px rgba(0,0,0,0.02);
  position: relative;
  z-index: 100; /* 保证导航栏在最上层 */
}

.header-content {
  max-width: 1400px;
  margin: 0 auto;
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.logo-text { font-weight: bold; font-size: 18px; color: #333; }

/* 导航菜单 */
.nav-menu { display: flex; gap: 30px; height: 100%; align-items: center; }

/* 导航项基础样式 */
.nav-item {
  font-size: 14px; color: #333; cursor: pointer; display: flex; align-items: center;
  height: 100%; position: relative; /* 关键：给下拉菜单定位 */
}
.nav-item .arrow { font-size: 10px; margin-left: 4px; color: #999; transition: transform 0.3s;}
.nav-item:hover { color: #409eff; }
.nav-item:hover .arrow { transform: rotate(180deg); }

/* 下拉菜单样式 */
.dropdown-menu {
  display: none; /* 默认隐藏 */
  position: absolute;
  top: 60px; /* 导航栏高度 */
  left: 50%;
  transform: translateX(-50%);
  background: white;
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
  border-radius: 4px;
  border: 1px solid #eee;
  min-width: 100px;
  padding: 5px 0;
  z-index: 200;
}

/* 鼠标悬停显示下拉 */
.dropdown-trigger:hover .dropdown-menu {
  display: block;
}

.dropdown-option {
  padding: 10px 15px;
  color: #333;
  text-align: center;
  white-space: nowrap;
}
.dropdown-option:hover {
  background-color: #f5f7fa;
  color: #409eff;
}

/* 右侧按钮 */
.right-actions { display: flex; align-items: center; gap: 20px; }
.text-link { font-size: 14px; color: #666; text-decoration: none; }
.text-link:hover { color: #333; }
.login-btn-pill { background-color: #409eff; color: white; border: none; padding: 6px 20px; border-radius: 20px; font-size: 13px; cursor: pointer; }
.login-btn-pill:hover { background-color: #66b1ff; }

main { min-height: calc(100vh - 60px); }
</style>