import { createRouter, createWebHistory } from 'vue-router';
import HomeView from '../components/HomeView.vue';
import AIGCView from '../components/AIGCView.vue';
import MultiModalSearch from '../components/MultiModalSearch.vue';
import ResourceUpload from '../components/ResourceUpload.vue';
import AnnotationTasks from '../components/AnnotationTasks.vue';
import SearchView from '../components/SearchView.vue';
import Login from '../components/Login.vue';
import ResourceDetail from '../components/ResourceDetail.vue';
import DashboardView from '../components/DashboardView.vue';
import UserManagement from '../components/UserManagement.vue';
import SecondaryCreationView from '../components/SecondaryCreationView.vue';
import MessageView from '../components/MessageView.vue';

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: Login,
    meta: { requiresAuth: false }
  },
  {
    path: '/',
    name: 'Home',
    component: HomeView,
    meta: { requiresAuth: true }
  },
  {
    path: '/aigc',
    name: 'AIGC',
    component: AIGCView,
    meta: { requiresAuth: true }
  },
  {
    path: '/multimodal',
    name: 'MultiModal',
    component: MultiModalSearch,
    meta: { requiresAuth: true }
  },
  {
    path: '/upload',
    name: 'Upload',
    component: ResourceUpload,
    meta: { requiresAuth: true }
  },
  {
    path: '/annotation',
    name: 'Annotation',
    component: AnnotationTasks,
    meta: { requiresAuth: true }
  },
  {
    path: '/search',
    name: 'Search',
    component: SearchView,
    meta: { requiresAuth: true }
  },
  {
    path: '/resource/detail',
    name: 'ResourceDetail',
    component: ResourceDetail,
    meta: { requiresAuth: true }
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: DashboardView,
    meta: { requiresAuth: true, requiresAdmin: true }
  },
  {
    path: '/users',
    name: 'UserManagement',
    component: UserManagement,
    meta: { requiresAuth: true, requiresSuperAdmin: true }
  },
  {
    path: '/secondary-creation',
    name: 'SecondaryCreation',
    component: SecondaryCreationView,
    meta: { requiresAuth: true }
  },
  {
    path: '/messages',
    name: 'Messages',
    component: MessageView,
    meta: { requiresAuth: true }
  }
];

const router = createRouter({
  history: createWebHistory(),
  routes
});

// 路由守卫：检查登录状态和权限
router.beforeEach((to, from, next) => {
  // 使用sessionStorage保存当前会话的登录状态，刷新页面后会自动清空，需要重新登录
  const userInfoStr = sessionStorage.getItem('userInfo');
  let userInfo = null;
  
  if (userInfoStr) {
    try {
      userInfo = JSON.parse(userInfoStr);
    } catch (e) {
    }
  }
  
  // 如果路由需要认证
  if (to.meta.requiresAuth) {
    if (!userInfo) {
      // 未登录，跳转到登录页
      next('/login');
      return;
    }
    
    // 如果路由需要管理员权限
    if (to.meta.requiresAdmin && userInfo.role !== '管理员' && userInfo.role !== '超级管理员') {
      next('/');
      return;
    }
    
    // 如果路由需要超级管理员权限
    if (to.meta.requiresSuperAdmin && userInfo.role !== '超级管理员') {
      next('/');
      return;
    }
    
    // 不再在路由守卫中记录访问日志，只在登录成功时记录一次
  } else {
    // 如果访问登录页且已登录（sessionStorage中有userInfo），跳转到首页
    // 注意：sessionStorage在刷新后会清空，所以这里检查的是当前会话状态
    if (to.path === '/login' && userInfo) {
      next('/');
      return;
    }
  }
  
  // 允许访问
  next();
});

// 导出路由实例
export default router;

