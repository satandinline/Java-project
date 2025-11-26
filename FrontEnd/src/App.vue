<template>
  <div id="app">
    <nav class="navbar">
      <div class="logo">文化资源管理系统</div>
      <div class="nav-links">
        <a href="#" @click.prevent="activeView = 'upload'">资源上传</a>
        <a href="#" @click.prevent="activeView = 'annotation'">标注任务</a>
        <a href="#" @click.prevent="handleLogout" v-if="isLoggedIn">退出登录</a>
        <a href="#" @click.prevent="activeView = 'login'" v-if="!isLoggedIn">登录/注册</a>
      </div>
    </nav>
    
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
import Login from './components/Login.vue'; // 假设已存在登录组件

const activeView = ref('login');
const userInfo = ref(null);

onMounted(() => {
  // 检查本地存储中的登录状态
  const savedUser = localStorage.getItem('userInfo');
  if (savedUser) {
    userInfo.value = JSON.parse(savedUser);
    activeView.value = 'upload';
  }
});

const isLoggedIn = computed(() => {
  return !!userInfo.value;
});

const currentComponent = computed(() => {
  switch (activeView.value) {
    case 'upload':
      return ResourceUpload;
    case 'annotation':
      return AnnotationTasks;
    case 'login':
      return Login;
    default:
      return Login;
  }
});

const handleLoginSuccess = (userData) => {
  userInfo.value = userData;
  localStorage.setItem('userInfo', JSON.stringify(userData));
  activeView.value = 'upload';
};

const handleLogout = () => {
  userInfo.value = null;
  localStorage.removeItem('userInfo');
  activeView.value = 'login';
};
</script>

<style>
/* 保留原有的样式并添加导航栏样式 */
.navbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 15px 30px;
  background-color: #35495e;
  color: white;
}

.logo {
  font-size: 1.5rem;
  font-weight: bold;
}

.nav-links {
  display: flex;
  gap: 20px;
}

.nav-links a {
  color: white;
  text-decoration: none;
  padding: 5px 10px;
  border-radius: 4px;
}

.nav-links a:hover {
  background-color: #4a6278;
}

main {
  padding: 20px;
}
</style>
