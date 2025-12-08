<template>
  <div class="login-wrapper">
    <div class="login-box">
      <h2>公共文化资源系统</h2>
      <p class="subtitle">{{ isRegisterMode ? '用户注册' : '用户登录' }}</p>
      
      <form @submit.prevent="isRegisterMode ? handleRegister() : handleLogin()">
        <div class="input-group">
          <label>用户名</label>
          <input 
            type="text" 
            v-model="username" 
            placeholder="请输入用户名（至少3个字符）"
            required
            :disabled="isLoading"
          >
        </div>
        
        <div class="input-group">
          <label>密码</label>
          <input 
            type="password" 
            v-model="password" 
            placeholder="请输入密码（至少6个字符）"
            required
            :disabled="isLoading"
          >
        </div>
        
        <div v-if="errorMessage" class="error-message">
          {{ errorMessage }}
        </div>
        
        <button type="submit" class="submit-btn" :disabled="isLoading">
          <span v-if="isLoading">处理中...</span>
          <span v-else>{{ isRegisterMode ? '立即注册' : '立即登录' }}</span>
        </button>
      </form>
      
      <div class="switch-mode">
        <span v-if="!isRegisterMode">还没有账号？</span>
        <span v-else>已有账号？</span>
        <a href="#" @click.prevent="toggleMode" class="switch-link">
          {{ isRegisterMode ? '立即登录' : '立即注册' }}
        </a>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';

const username = ref('');
const password = ref('');
const isRegisterMode = ref(false);
const isLoading = ref(false);
const errorMessage = ref('');

// 定义向父组件(App.vue)发送事件的方法
const emit = defineEmits(['login-success']);

const toggleMode = () => {
  isRegisterMode.value = !isRegisterMode.value;
  errorMessage.value = '';
  username.value = '';
  password.value = '';
};

const handleLogin = async () => {
  if (!username.value.trim() || !password.value.trim()) {
    errorMessage.value = '请输入用户名和密码';
    return;
  }

  isLoading.value = true;
  errorMessage.value = '';

  try {
    const response = await fetch('/api/auth/login', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        username: username.value.trim(),
        password: password.value
      })
    });

    const result = await response.json();

    if (result.success) {
      // 保存用户信息到本地存储
      const userInfo = {
        id: result.user_info.id,
        username: result.user_info.username,
        role: result.user_info.role
      };
      localStorage.setItem('userInfo', JSON.stringify(userInfo));

      // 通知 App.vue 切换页面
      emit('login-success', userInfo);
    } else {
      errorMessage.value = result.message || '登录失败，请重试';
    }
  } catch (error) {
    console.error('登录失败:', error);
    errorMessage.value = '网络错误，请检查后端服务器是否启动';
  } finally {
    isLoading.value = false;
  }
};

const handleRegister = async () => {
  if (!username.value.trim() || !password.value.trim()) {
    errorMessage.value = '请输入用户名和密码';
    return;
  }

  if (username.value.trim().length < 3) {
    errorMessage.value = '用户名至少需要3个字符';
    return;
  }

  if (password.value.length < 6) {
    errorMessage.value = '密码至少需要6个字符';
    return;
  }

  isLoading.value = true;
  errorMessage.value = '';

  try {
    const response = await fetch('/api/auth/register', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        username: username.value.trim(),
        password: password.value
      })
    });

    const result = await response.json();

    if (result.success) {
      // 注册成功后自动登录
      errorMessage.value = '';
      await handleLogin();
    } else {
      errorMessage.value = result.message || '注册失败，请重试';
    }
  } catch (error) {
    console.error('注册失败:', error);
    errorMessage.value = '网络错误，请检查后端服务器是否启动';
  } finally {
    isLoading.value = false;
  }
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

.submit-btn:hover:not(:disabled) {
  background-color: #3aa876;
}

.submit-btn:disabled {
  background-color: #ccc;
  cursor: not-allowed;
}

.error-message {
  margin-top: 10px;
  padding: 10px;
  background-color: #fee;
  color: #c33;
  border-radius: 4px;
  font-size: 13px;
  text-align: left;
}

.switch-mode {
  margin-top: 20px;
  font-size: 14px;
  color: #666;
}

.switch-link {
  color: #42b983;
  text-decoration: none;
  margin-left: 5px;
  font-weight: 500;
}

.switch-link:hover {
  text-decoration: underline;
}
</style>