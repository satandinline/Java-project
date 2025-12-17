import { createRouter, createWebHistory } from 'vue-router';
import HomeView from '../components/HomeView.vue';
import AIGCView from '../components/AIGCView.vue';
import MultiModalSearch from '../components/MultiModalSearch.vue';
import ResourceUpload from '../components/ResourceUpload.vue';
import AnnotationTasks from '../components/AnnotationTasks.vue';
import SearchView from '../components/SearchView.vue';
import Login from '../components/Login.vue';
import ResourceDetail from '../components/ResourceDetail.vue';

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
  }
];

const router = createRouter({
  history: createWebHistory(),
  routes
});

// 路由守卫：检查登录状态
router.beforeEach((to, from, next) => {
  console.log('路由守卫:', { from: from.path, to: to.path, requiresAuth: to.meta.requiresAuth });
  const userInfo = localStorage.getItem('userInfo');
  
  // 如果路由需要认证
  if (to.meta.requiresAuth) {
    if (!userInfo) {
      // 未登录，跳转到登录页
      console.log('未登录，跳转到登录页');
      next('/login');
      return;
    }
  } else {
    // 如果访问登录页且已登录，跳转到首页
    if (to.path === '/login' && userInfo) {
      console.log('已登录，跳转到首页');
      next('/');
      return;
    }
  }
  
  // 允许访问
  console.log('允许访问:', to.path);
  next();
});

// 导出路由实例
export default router;

