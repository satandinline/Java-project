<template>
  <div class="login-wrapper">
    <div class="login-box">
      <h2>公共文化资源系统</h2>
      <p class="subtitle">管理员登录</p>
      
      <form @submit.prevent="handleLogin">
        <div class="input-group">
          <label>账号</label>
          <input 
            type="text" 
            v-model="username" 
            placeholder="admin"
            required
          >
        </div>
        
        <div class="input-group">
          <label>密码</label>
          <input 
            type="password" 
            v-model="password" 
            placeholder="任意字符即可登录"
            required
          >
        </div>
        
        <button type="submit" class="submit-btn">立即登录</button>
      </form>
      
      <div class="tips">
        * 演示环境：输入任意账号密码即可进入
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';

const username = ref('');
const password = ref('');

// 定义向父组件(App.vue)发送事件的方法
const emit = defineEmits(['login-success']);

const handleLogin = () => {
  // 模拟登录请求
  console.log('正在登录...');
  
  // 构造一个模拟的用户对象
  const mockUser = {
    id: 'admin_001',
    username: username.value || 'Admin',
    role: 'administrator',
    token: 'mock-token-xyz-123'
  };

  // 1. 保存到本地存储（防止刷新后掉线）
  localStorage.setItem('userInfo', JSON.stringify(mockUser));

  // 2. 通知 App.vue 切换页面
  emit('login-success', mockUser);
};
</script>

<style scoped>
.login-wrapper {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 80vh;
  background-color: #f0f2f5;
}

.login-box {
  width: 400px;
  padding: 40px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  text-align: center;
}

h2 {
  color: #333;
  margin-bottom: 10px;
}

.subtitle {
  color: #666;
  margin-bottom: 30px;
  font-size: 14px;
}

.input-group {
  text-align: left;
  margin-bottom: 20px;
}

.input-group label {
  display: block;
  margin-bottom: 8px;
  color: #333;
  font-weight: 500;
}

.input-group input {
  width: 100%;
  padding: 10px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 14px;
  box-sizing: border-box; 
}

.input-group input:focus {
  border-color: #42b983;
  outline: none;
}

.submit-btn {
  width: 100%;
  padding: 12px;
  background-color: #42b983;
  color: white;
  border: none;
  border-radius: 4px;
  font-size: 16px;
  cursor: pointer;
  transition: background 0.3s;
}

.submit-btn:hover {
  background-color: #3aa876;
}

.tips {
  margin-top: 20px;
  font-size: 12px;
  color: #999;
}
</style>