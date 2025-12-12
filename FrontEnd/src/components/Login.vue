<template>
  <div class="login-wrapper">
    <div class="login-box">
      <h2>公共文化资源系统</h2>
      <p class="subtitle">{{ isRegisterMode ? '用户注册' : '用户登录' }}</p>
      
      <!-- 登录表单 -->
      <form v-if="!isRegisterMode && !showForgotPassword" @submit.prevent="handleLogin">
        <div class="input-group">
          <label>用户名</label>
          <input 
            type="text" 
            v-model="username" 
            placeholder="请输入用户名（至少3个字符，只能包含数字和英文字母）"
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
          <span v-if="isLoading">登录中...</span>
          <span v-else>立即登录</span>
        </button>
      </form>
      
      <!-- 注册表单 -->
      <form v-if="isRegisterMode && !showForgotPassword" @submit.prevent="handleRegister" enctype="multipart/form-data">
        <div class="input-group">
          <label>用户名</label>
          <input 
            type="text" 
            v-model="username" 
            @input="validateUsername"
            placeholder="请输入用户名（至少3个字符，只能包含数字和英文字母）"
            required
            :disabled="isLoading"
          >
          <div v-if="usernameError" class="error-message" style="margin-top: 5px;">
            {{ usernameError }}
          </div>
        </div>
        
        <div class="input-group">
          <label>密码</label>
          <input 
            type="password" 
            v-model="password" 
            @input="validatePassword"
            placeholder="请输入密码（至少6个字符，只能包含英文字母、数字或中英文符号）"
            required
            :disabled="isLoading"
          >
          <div v-if="passwordError" class="error-message" style="margin-top: 5px;">
            {{ passwordError }}
          </div>
        </div>
        
        <div class="input-group">
          <label>昵称（可选，不填将随机生成）</label>
          <input 
            type="text" 
            v-model="nickname" 
            placeholder="请输入昵称"
            :disabled="isLoading"
          >
        </div>
        
        <div class="input-group">
          <label>头像（可选）</label>
          <div class="avatar-upload">
            <img v-if="avatarPreview" :src="avatarPreview" class="avatar-preview" />
            <img v-else :src="defaultAvatarUrl" class="avatar-preview" />
            <label class="avatar-upload-btn">
              <input 
                type="file" 
                accept="image/*" 
                @change="handleAvatarChange"
                style="display: none;"
                :disabled="isLoading"
              />
              选择头像
            </label>
          </div>
        </div>
        
        <div class="input-group">
          <label>自定义问题（用于找回密码，可选）</label>
          <input 
            type="text" 
            v-model="securityQuestion" 
            placeholder="例如：我的出生地是哪里？"
            :disabled="isLoading"
          >
        </div>
        
        <div class="input-group" v-if="securityQuestion">
          <label>问题答案</label>
          <input 
            type="text" 
            v-model="securityAnswer" 
            placeholder="请输入问题答案"
            :disabled="isLoading"
          >
        </div>
        
        <div v-if="errorMessage" class="error-message">
          {{ errorMessage }}
        </div>
        
        <button type="submit" class="submit-btn" :disabled="isLoading">
          <span v-if="isLoading">注册中...</span>
          <span v-else>立即注册</span>
        </button>
      </form>
      
      <!-- 忘记密码 -->
      <div v-if="showForgotPassword" class="forgot-password">
        <div v-if="!securityQuestionReceived">
          <div class="input-group">
            <label>用户名</label>
            <input 
              type="text" 
              v-model="forgotUsername" 
              placeholder="请输入用户名"
              required
              :disabled="isLoading"
            >
          </div>
          <div v-if="errorMessage" class="error-message">
            {{ errorMessage }}
          </div>
          <button @click="getSecurityQuestion" class="submit-btn" :disabled="isLoading">
            <span v-if="isLoading">查询中...</span>
            <span v-else>下一步</span>
          </button>
        </div>
        
        <div v-else-if="!answerVerified">
          <div class="security-question-box">
            <p class="question-label">安全问题：</p>
            <p class="question-text">{{ securityQuestionReceived }}</p>
          </div>
          <div class="input-group">
            <label>答案</label>
            <input 
              type="text" 
              v-model="securityAnswerInput" 
              placeholder="请输入答案"
              required
              :disabled="isLoading"
            >
          </div>
          <div v-if="errorMessage" class="error-message">
            {{ errorMessage }}
          </div>
          <button @click="verifyAnswer" class="submit-btn" :disabled="isLoading">
            <span v-if="isLoading">验证中...</span>
            <span v-else>验证</span>
          </button>
        </div>
        
        <div v-else>
          <div class="input-group">
            <label>新密码</label>
            <input 
              type="password" 
              v-model="newPassword" 
              placeholder="请输入新密码（至少6个字符）"
              required
              :disabled="isLoading"
            >
          </div>
          <div class="input-group">
            <label>确认新密码</label>
            <input 
              type="password" 
              v-model="confirmPassword" 
              placeholder="请再次输入新密码"
              required
              :disabled="isLoading"
            >
          </div>
          <div v-if="errorMessage" class="error-message">
            {{ errorMessage }}
          </div>
          <button @click="verifyAnswer" class="submit-btn" :disabled="isLoading">
            <span v-if="isLoading">重置中...</span>
            <span v-else>重置密码</span>
          </button>
        </div>
        
        <div class="back-link">
          <a href="#" @click.prevent="showForgotPassword = false; resetForgotPassword()">返回登录</a>
        </div>
      </div>
      
      <div class="switch-mode" v-if="!showForgotPassword">
        <span v-if="!isRegisterMode">
          还没有账号？
          <a href="#" @click.prevent="toggleMode" class="switch-link">立即注册</a>
          <span style="margin: 0 8px;">|</span>
          <a href="#" @click.prevent="showForgotPassword = true" class="switch-link">忘记密码</a>
        </span>
        <span v-else>
          已有账号？
          <a href="#" @click.prevent="toggleMode" class="switch-link">立即登录</a>
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { useRouter } from 'vue-router';

// 定义向父组件(App.vue)发送事件的方法
const emit = defineEmits(['login-success']);

// 初始化路由
const router = useRouter();

// 默认头像URL（使用字符串，避免Vite将其作为模块导入）
const defaultAvatarUrl = '/default.jpg';

// 响应式数据
const username = ref('');
const password = ref('');
const nickname = ref('');
const avatarFile = ref(null);
const avatarPreview = ref(null);
const securityQuestion = ref('');
const securityAnswer = ref('');
const isRegisterMode = ref(false);
const isLoading = ref(false);
const errorMessage = ref('');
const usernameError = ref('');
const passwordError = ref('');

// 忘记密码相关
const showForgotPassword = ref(false);
const forgotUsername = ref('');
const securityQuestionReceived = ref('');
const securityAnswerInput = ref('');
const answerVerified = ref(false);
const newPassword = ref('');
const confirmPassword = ref('');

const validateUsername = () => {
  usernameError.value = '';
  if (!username.value.trim()) {
    return;
  }
  
  if (username.value.trim().length < 3) {
    usernameError.value = '用户名至少需要3个字符';
    return;
  }
  
  // 验证用户名只能包含数字和英文字母
  const usernameRegex = /^[a-zA-Z0-9]+$/;
  if (!usernameRegex.test(username.value.trim())) {
    usernameError.value = '用户名只能包含数字和英文字母';
    return;
  }
};

const validatePassword = () => {
  passwordError.value = '';
  if (!password.value) {
    return;
  }
  
  if (password.value.length < 6) {
    passwordError.value = '密码至少需要6个字符';
    return;
  }
  
  // 验证密码只能包含英文字母、数字或中英文符号
  // 中英文符号包括：!@#$%^&*()_+-=[]{}|;:'",.<>?/~`等
  const passwordRegex = /^[\u0020-\u007E\u4e00-\u9fa5]+$/;
  if (!passwordRegex.test(password.value)) {
    passwordError.value = '密码只能包含英文字母、数字或中英文符号';
    return;
  }
};

const toggleMode = () => {
  isRegisterMode.value = !isRegisterMode.value;
  errorMessage.value = '';
  usernameError.value = '';
  passwordError.value = '';
  username.value = '';
  password.value = '';
  nickname.value = '';
  avatarFile.value = null;
  avatarPreview.value = null;
  securityQuestion.value = '';
  securityAnswer.value = '';
};

const handleAvatarChange = (event) => {
  const file = event.target.files[0];
  if (file) {
    avatarFile.value = file;
    const reader = new FileReader();
    reader.onload = (e) => {
      avatarPreview.value = e.target.result;
    };
    reader.readAsDataURL(file);
  }
};

const resetForgotPassword = () => {
  forgotUsername.value = '';
  securityQuestionReceived.value = '';
  securityAnswerInput.value = '';
  answerVerified.value = false;
  newPassword.value = '';
  confirmPassword.value = '';
  errorMessage.value = '';
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
        nickname: result.user_info.nickname || result.user_info.username,
        avatar_path: result.user_info.avatar_path || '/default.jpg',
        role: result.user_info.role
      };
      localStorage.setItem('userInfo', JSON.stringify(userInfo));

      // 通知 App.vue 切换页面
      emit('login-success', userInfo);
      
      // 跳转到首页
      router.push('/');
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
  // 先进行验证
  validateUsername();
  validatePassword();
  
  if (usernameError.value || passwordError.value) {
    errorMessage.value = '请修正上述错误后重试';
    return;
  }
  
  if (!username.value.trim() || !password.value.trim()) {
    errorMessage.value = '请输入用户名和密码';
    return;
  }

  if (username.value.trim().length < 3) {
    errorMessage.value = '用户名至少需要3个字符';
    return;
  }

  // 验证用户名只能包含数字和英文字母
  const usernameRegex = /^[a-zA-Z0-9]+$/;
  if (!usernameRegex.test(username.value.trim())) {
    errorMessage.value = '用户名只能包含数字和英文字母';
    return;
  }

  if (password.value.length < 6) {
    errorMessage.value = '密码至少需要6个字符';
    return;
  }
  
  // 验证密码只能包含英文字母、数字或中英文符号
  const passwordRegex = /^[\u0020-\u007E\u4e00-\u9fa5]+$/;
  if (!passwordRegex.test(password.value)) {
    errorMessage.value = '密码只能包含英文字母、数字或中英文符号';
    return;
  }

  if (securityQuestion.value && !securityAnswer.value) {
    errorMessage.value = '如果设置了安全问题，必须提供答案';
    return;
  }

  isLoading.value = true;
  errorMessage.value = '';

  try {
    const formData = new FormData();
    formData.append('username', username.value.trim());
    formData.append('password', password.value);
    if (nickname.value.trim()) {
      formData.append('nickname', nickname.value.trim());
    }
    if (avatarFile.value) {
      formData.append('avatar', avatarFile.value);
    }
    if (securityQuestion.value.trim()) {
      formData.append('security_question', securityQuestion.value.trim());
      formData.append('security_answer', securityAnswer.value.trim());
    }

    const response = await fetch('/api/auth/register', {
      method: 'POST',
      body: formData
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

const getSecurityQuestion = async () => {
  if (!forgotUsername.value.trim()) {
    errorMessage.value = '请输入用户名';
    return;
  }

  isLoading.value = true;
  errorMessage.value = '';

  try {
    const response = await fetch('/api/auth/forgot-password/question', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        username: forgotUsername.value.trim()
      })
    });

    const result = await response.json();

    if (result.success) {
      securityQuestionReceived.value = result.security_question;
    } else {
      errorMessage.value = result.message || '获取安全问题失败';
    }
  } catch (error) {
    console.error('获取安全问题失败:', error);
    errorMessage.value = '网络错误，请检查后端服务器是否启动';
  } finally {
    isLoading.value = false;
  }
};

const verifyAnswer = async () => {
  if (!answerVerified.value) {
    // 第一步：验证答案
    if (!securityAnswerInput.value.trim()) {
      errorMessage.value = '请输入答案';
      return;
    }

    isLoading.value = true;
    errorMessage.value = '';

    try {
      const response = await fetch('/api/auth/forgot-password/verify', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          username: forgotUsername.value.trim(),
          answer: securityAnswerInput.value.trim()
        })
      });

      const result = await response.json();

      if (result.success) {
        answerVerified.value = true;
        errorMessage.value = '';
      } else {
        errorMessage.value = result.message || '答案错误';
      }
    } catch (error) {
      console.error('验证答案失败:', error);
      errorMessage.value = '网络错误，请检查后端服务器是否启动';
    } finally {
      isLoading.value = false;
    }
  } else {
    // 第二步：重置密码
    if (!newPassword.value || !confirmPassword.value) {
      errorMessage.value = '请输入新密码和确认密码';
      return;
    }

    if (newPassword.value.length < 6) {
      errorMessage.value = '密码至少需要6个字符';
      return;
    }

    if (newPassword.value !== confirmPassword.value) {
      errorMessage.value = '两次输入的密码不一致';
      return;
    }

    isLoading.value = true;
    errorMessage.value = '';

    try {
      const response = await fetch('/api/auth/forgot-password/reset', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          username: forgotUsername.value.trim(),
          answer: securityAnswerInput.value.trim(),
          new_password: newPassword.value.trim()
        })
      });

      const result = await response.json();

      if (result.success) {
        alert('密码重置成功，请使用新密码登录');
        // 返回登录界面
        showForgotPassword.value = false;
        resetForgotPassword();
      } else {
        errorMessage.value = result.message || '重置失败';
      }
    } catch (error) {
      console.error('重置密码失败:', error);
      errorMessage.value = '网络错误，请检查后端服务器是否启动';
    } finally {
      isLoading.value = false;
    }
  }
};

const resetPassword = async () => {
  if (!newPassword.value || !confirmPassword.value) {
    errorMessage.value = '请输入新密码和确认密码';
    return;
  }

  if (newPassword.value.length < 6) {
    errorMessage.value = '密码至少需要6个字符';
    return;
  }

  if (newPassword.value !== confirmPassword.value) {
    errorMessage.value = '两次输入的密码不一致';
    return;
  }

  isLoading.value = true;
  errorMessage.value = '';

  try {
    const response = await fetch('/api/auth/forgot-password/reset', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        username: forgotUsername.value.trim(),
        new_password: newPassword.value
      })
    });

    const result = await response.json();

    if (result.success) {
      errorMessage.value = '密码重置成功，请使用新密码登录';
      setTimeout(() => {
        showForgotPassword.value = false;
        resetForgotPassword();
      }, 2000);
    } else {
      errorMessage.value = result.message || '重置密码失败';
    }
  } catch (error) {
    console.error('重置密码失败:', error);
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
  min-height: 100vh;
  width: 100%;
  background-color: #f0f2f5;
  padding: 20px;
  box-sizing: border-box;
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

.avatar-upload {
  display: flex;
  align-items: center;
  gap: 15px;
}

.avatar-preview {
  width: 60px;
  height: 60px;
  border-radius: 50%;
  object-fit: cover;
  border: 2px solid #ddd;
}

.avatar-upload-btn {
  padding: 8px 16px;
  background: #f0f2f5;
  border: 1px solid #ddd;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  color: #666;
  transition: all 0.3s;
}

.avatar-upload-btn:hover {
  background: #e4e7ed;
  border-color: #42b983;
}

.security-question-box {
  background: #f5f7fa;
  padding: 15px;
  border-radius: 4px;
  margin-bottom: 20px;
  text-align: left;
}

.question-label {
  font-weight: 500;
  color: #333;
  margin-bottom: 8px;
}

.question-text {
  color: #666;
  font-size: 14px;
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

.back-link {
  margin-top: 15px;
  font-size: 14px;
}

.back-link a {
  color: #42b983;
  text-decoration: none;
}

.back-link a:hover {
  text-decoration: underline;
}
</style>
