import './assets/main.css'

import { createApp } from 'vue'
import App from './App.vue'
import router from './router'

console.log('main.js: 开始初始化应用');

try {
  const app = createApp(App);
  app.use(router);
  app.mount('#app');
  console.log('main.js: 应用已成功挂载');
} catch (error) {
  console.error('main.js: 应用初始化失败', error);
}
