<template>
  <div id="app">
    <!-- 顶部导航栏 -->
    <header class="main-header" v-if="isLoggedIn">
      <div class="header-content">
        <!-- 1. 修改 Logo 文字 -->
        <div class="brand">
          <span class="logo-text">公共文化资源系统</span>
        </div>


        <!-- 右侧 功能区 -->
        <div class="right-actions">
          <router-link to="/" class="text-link">首页</router-link>
          <router-link to="/search" class="text-link">AI检索</router-link>
          <router-link to="/aigc" class="text-link" style="font-weight: 600; color: #409eff;">AIGC</router-link>
          <router-link to="/multimodal" class="text-link">图文互搜</router-link>
          <router-link to="/upload" class="text-link">用户上传</router-link>
          <router-link to="/annotation" class="text-link">标注任务</router-link>
          
          <!-- 设置入口 -->
          <div class="settings-link" @click="showSettingsModal = true">
            <span>⚙️</span> 设置
          </div>
          
          <!-- 用户头像和昵称 -->
          <div class="user-profile">
            <div class="user-profile-content">
              <div class="user-avatar-container">
                <img :src="getAvatarUrl(userInfo?.avatar_path)" class="user-avatar" alt="头像" @error="handleAvatarError" />
              </div>
              <div class="user-nickname">{{ userInfo?.nickname || userInfo?.username || '用户' }}</div>
            </div>
          </div>
        </div>
        
        <!-- 设置对话框 -->
        <div v-if="showSettingsModal" class="modal-overlay" @click="showSettingsModal = false">
          <div class="modal-content settings-modal" @click.stop>
            <h3>设置</h3>
            <div class="settings-tabs">
              <div class="tab-item" :class="{ active: settingsTab === 'avatar' }" @click="settingsTab = 'avatar'">
                🖼️ 更换头像
              </div>
              <div class="tab-item" :class="{ active: settingsTab === 'password' }" @click="handlePasswordTabClick">
                🔒 修改密码
              </div>
              <div class="tab-item" :class="{ active: settingsTab === 'security' }" @click="handleSecurityTabClick">
                🔐 更换二级问题
              </div>
              <div class="tab-item logout-item" @click="handleLogout">
                🚪 退出登录
              </div>
            </div>
            
            <!-- 更换头像 -->
            <div v-if="settingsTab === 'avatar'" class="settings-panel">
              <div class="input-group">
                <label>选择操作</label>
                <div class="avatar-options">
                  <button @click="handleUploadNewAvatar" class="option-btn">
                    <span>📤</span> 上传新头像
                  </button>
                  <button @click="handleUseDefaultAvatar" class="option-btn">
                    <span>🖼️</span> 使用默认头像
                  </button>
                </div>
              </div>
              <div v-if="showAvatarUpload" class="input-group">
                <label>选择头像文件</label>
                <input 
                  type="file" 
                  ref="avatarFileInput"
                  accept="image/*" 
                  @change="handleAvatarFileChange"
                  style="margin-top: 8px;"
                />
                <!-- 头像裁剪界面 -->
                <div v-if="showAvatarCrop" class="avatar-crop-container">
                  <div class="avatar-crop-frame">
                    <div 
                      class="avatar-crop-image-wrapper"
                      @mousedown="handleAvatarDragStart"
                      @mousemove="handleAvatarDrag"
                      @mouseup="handleAvatarDragEnd"
                      @mouseleave="handleAvatarDragEnd"
                    >
                      <img 
                        :src="newAvatarPreview" 
                        class="avatar-crop-image"
                        :style="{
                          transform: `translate(-50%, -50%) scale(${avatarScale}) translate(${avatarOffsetX / avatarScale}px, ${avatarOffsetY / avatarScale}px)`,
                          cursor: isDragging ? 'grabbing' : 'grab',
                          maxWidth: 'none',
                          maxHeight: 'none'
                        }"
                        draggable="false"
                      />
                    </div>
                    <div class="avatar-crop-overlay"></div>
                  </div>
                  <div class="avatar-crop-controls">
                    <label>缩放：</label>
                    <button @click="handleAvatarZoom(-0.1)" :disabled="avatarScale <= 0.1">缩小</button>
                    <span style="margin: 0 10px;">{{ Math.round(avatarScale * 100) }}%</span>
                    <button @click="handleAvatarZoom(0.1)" :disabled="avatarScale >= 3.0">放大</button>
                    <p style="font-size: 12px; color: #999; margin-top: 8px;">提示：可以拖动图片调整位置，可以放大缩小</p>
                  </div>
                </div>
              </div>
              <div v-if="changeAvatarError" class="error-message">
                {{ changeAvatarError }}
              </div>
              <div v-if="changeAvatarSuccess" class="success-message">
                {{ changeAvatarSuccess }}
              </div>
              <div class="modal-actions">
                <button v-if="showAvatarCrop" @click="handleConfirmAvatarUpload" class="submit-btn">确认更换</button>
                <button v-else-if="showAvatarUpload && newAvatarFile" @click="handleConfirmAvatarUpload" class="submit-btn">确认上传</button>
                <button @click="showSettingsModal = false" class="cancel-btn">关闭</button>
              </div>
            </div>
            
            <!-- 修改密码 -->
            <div v-if="settingsTab === 'password'" class="settings-panel">
              <div v-if="!useSecurityQuestionForPassword" class="input-group">
                <div style="margin-bottom: 10px;">
                  <a href="#" @click.prevent="useSecurityQuestionForPassword = true" style="color: #409eff; font-size: 12px;">忘记原密码？使用二级密码验证</a>
                </div>
                <label>旧密码</label>
                <input type="password" v-model="oldPassword" placeholder="请输入旧密码" style="ime-mode: disabled;" />
              </div>
              <div v-else class="input-group">
                <div style="margin-bottom: 10px;">
                  <a href="#" @click.prevent="useSecurityQuestionForPassword = false" style="color: #409eff; font-size: 12px;">使用原密码验证</a>
                </div>
                <label>验证二级密码答案</label>
                <p v-if="currentSecurityQuestion" class="security-question-display">当前问题：{{ currentSecurityQuestion }}</p>
                <p v-else class="security-question-display" style="color: #f56c6c;">您尚未设置二级问题，无法使用此方式</p>
                <input 
                  type="text" 
                  v-model="securityAnswerForPassword" 
                  placeholder="请输入二级密码答案" 
                  :disabled="!currentSecurityQuestion"
                  style="ime-mode: active;"
                />
              </div>
              <div class="input-group">
                <label>新密码</label>
                <input type="password" v-model="newPassword" placeholder="请输入新密码（至少6个字符）" style="ime-mode: disabled;" />
              </div>
              <div class="input-group">
                <label>确认新密码</label>
                <input type="password" v-model="confirmNewPassword" placeholder="请再次输入新密码" style="ime-mode: disabled;" />
              </div>
              <div v-if="changePasswordError" class="error-message">
                {{ changePasswordError }}
              </div>
              <div v-if="changePasswordSuccess" class="success-message">
                {{ changePasswordSuccess }}
              </div>
              <div class="modal-actions">
                <button @click="handleChangePassword" class="submit-btn">确认修改</button>
                <button @click="showSettingsModal = false" class="cancel-btn">关闭</button>
              </div>
            </div>
            
            <!-- 更换二级问题 -->
            <div v-if="settingsTab === 'security'" class="settings-panel">
              <div v-if="!currentSecurityQuestion" class="input-group">
                <p class="security-question-display">您尚未设置二级问题</p>
                <label>新问题</label>
                <input type="text" v-model="newSecurityQuestion" placeholder="请输入新的安全问题" style="ime-mode: active;" />
                <label style="margin-top: 12px;">新答案</label>
                <input type="text" v-model="newSecurityAnswer" placeholder="请输入新问题的答案" style="ime-mode: active;" />
                <div v-if="changeSecurityError" class="error-message">
                  {{ changeSecurityError }}
                </div>
                <div v-if="changeSecuritySuccess" class="success-message">
                  {{ changeSecuritySuccess }}
                </div>
                <div class="modal-actions">
                  <button @click="handleChangeSecurityQuestion" class="submit-btn">确认设置</button>
                  <button @click="showSettingsModal = false" class="cancel-btn">关闭</button>
                </div>
              </div>
              <div v-else-if="!securityAnswerVerified" class="input-group">
                <label>验证原答案</label>
                <p class="security-question-display">当前问题：{{ currentSecurityQuestion }}</p>
                <input type="text" v-model="oldSecurityAnswer" placeholder="请输入原问题的答案" style="ime-mode: active;" />
                <div v-if="securityVerifyError" class="error-message">
                  {{ securityVerifyError }}
                </div>
                <div class="modal-actions">
                  <button @click="handleVerifySecurityAnswer" class="submit-btn">验证</button>
                  <button @click="showSettingsModal = false" class="cancel-btn">关闭</button>
                </div>
              </div>
              <div v-else class="input-group">
                <label>新问题</label>
                <input type="text" v-model="newSecurityQuestion" placeholder="请输入新的安全问题" style="ime-mode: active;" />
                <label style="margin-top: 12px;">新答案</label>
                <input type="text" v-model="newSecurityAnswer" placeholder="请输入新问题的答案" style="ime-mode: active;" />
                <div v-if="changeSecurityError" class="error-message">
                  {{ changeSecurityError }}
                </div>
                <div v-if="changeSecuritySuccess" class="success-message">
                  {{ changeSecuritySuccess }}
                </div>
                <div class="modal-actions">
                  <button @click="handleChangeSecurityQuestion" class="submit-btn">确认更换</button>
                  <button @click="showSettingsModal = false" class="cancel-btn">关闭</button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </header>
    
    <main>
      <router-view></router-view>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';

const router = useRouter();

// 登录状态
const userInfo = ref(null);
const showSettingsModal = ref(false);
const settingsTab = ref('avatar'); // 'avatar', 'password', 'security'

// 修改密码相关
const oldPassword = ref('');
const newPassword = ref('');
const confirmNewPassword = ref('');
const changePasswordError = ref('');
const changePasswordSuccess = ref('');

// 更换头像相关
const showChangeAvatar = ref(false);
const showAvatarUpload = ref(false);
const showAvatarCrop = ref(false);
const newAvatarFile = ref(null);
const newAvatarPreview = ref(null);
const avatarFileInput = ref(null);
const changeAvatarError = ref('');
const changeAvatarSuccess = ref('');
const avatarScale = ref(1.0);
const avatarOffsetX = ref(0);
const avatarOffsetY = ref(0);
const isDragging = ref(false);
const dragStartX = ref(0);
const dragStartY = ref(0);
const originalImageSize = ref({ width: 0, height: 0 });

// 更换二级问题相关
const currentSecurityQuestion = ref('');
const oldSecurityAnswer = ref('');
const securityAnswerVerified = ref(false);
const securityVerifyError = ref('');
const newSecurityQuestion = ref('');
const newSecurityAnswer = ref('');
const changeSecurityError = ref('');
const changeSecuritySuccess = ref('');

// 修改密码相关（使用二级密码）
const useSecurityQuestionForPassword = ref(false);
const securityAnswerForPassword = ref('');

onMounted(() => {
  console.log('App.vue mounted');
  const savedUser = localStorage.getItem('userInfo');
  if (savedUser) {
    try {
      const parsedUser = JSON.parse(savedUser);
      // 验证用户信息是否有效（检查必要字段）
      if (!parsedUser || !parsedUser.id || !parsedUser.username) {
        console.log('localStorage中的用户信息无效，已清除');
        localStorage.removeItem('userInfo');
        userInfo.value = null;
        return;
      }
      userInfo.value = parsedUser;
      console.log('用户信息已加载:', userInfo.value);
    } catch (e) {
      console.error('解析用户信息失败:', e);
      localStorage.removeItem('userInfo');
      userInfo.value = null;
    }
  } else {
    console.log('未找到用户信息，需要登录');
  }
});

const isLoggedIn = computed(() => !!userInfo.value);

// 监听路由变化，更新用户信息
router.afterEach(() => {
  // 当路由变化时，重新从localStorage读取用户信息
  const savedUser = localStorage.getItem('userInfo');
  if (savedUser) {
    try {
      const parsedUser = JSON.parse(savedUser);
      // 验证用户信息是否有效（检查必要字段）
      if (!parsedUser || !parsedUser.id || !parsedUser.username) {
        console.log('localStorage中的用户信息无效，已清除');
        localStorage.removeItem('userInfo');
        userInfo.value = null;
        return;
      }
      userInfo.value = parsedUser;
    } catch (e) {
      console.error('解析用户信息失败:', e);
      localStorage.removeItem('userInfo');
      userInfo.value = null;
    }
  } else {
    userInfo.value = null;
  }
});

const handleLoginSuccess = (userData) => {
  userInfo.value = userData || null;
  if (userInfo.value) {
    // 确保包含所有必要字段
    if (!userInfo.value.nickname) {
      userInfo.value.nickname = userInfo.value.username;
    }
    if (!userInfo.value.avatar_path || userInfo.value.avatar_path === './default.jpg') {
      userInfo.value.avatar_path = '/default.jpg';
    }
    localStorage.setItem('userInfo', JSON.stringify(userInfo.value));
    router.push('/');
  }
};

const getAvatarUrl = (avatarPath) => {
  if (!avatarPath) return '/default.jpg';
  // 如果已经是完整URL，直接返回
  if (avatarPath.startsWith('http://') || avatarPath.startsWith('https://')) {
    return avatarPath;
  }
  // 如果以 / 开头，直接返回（已经是正确的路径格式）
  if (avatarPath.startsWith('/')) {
    return avatarPath;
  }
  // 如果以 ./ 开头，转换为 / 开头
  if (avatarPath.startsWith('./')) {
    return avatarPath.replace('./', '/');
  }
  // 其他情况，添加 / 前缀
  return '/' + avatarPath;
};

const handleAvatarError = (event) => {
  // 如果头像加载失败，使用默认头像
  event.target.src = '/default.jpg';
};

const handleChangeAvatarClick = () => {
  // 显示更换头像对话框
  showChangeAvatar.value = true;
  showSettingsMenu.value = false;
  showAvatarUpload.value = false;
  newAvatarFile.value = null;
  newAvatarPreview.value = null;
  changeAvatarError.value = '';
  changeAvatarSuccess.value = '';
};

const handleUploadNewAvatar = () => {
  // 显示上传选项
  showAvatarUpload.value = true;
  changeAvatarError.value = '';
  changeAvatarSuccess.value = '';
};

const handleAvatarFileChange = (event) => {
  const file = event.target.files[0];
  if (file) {
    newAvatarFile.value = file;
    // 创建预览
    const reader = new FileReader();
    reader.onload = (e) => {
      newAvatarPreview.value = e.target.result;
      // 获取图片尺寸
      const img = new Image();
      img.onload = () => {
        originalImageSize.value = { width: img.width, height: img.height };
        // 显示裁剪界面
        showAvatarCrop.value = true;
        
        // 计算合适的初始缩放比例，使图片能够完全显示在200x200的裁剪框内
        const cropSize = 200;
        const scaleX = cropSize / img.width;
        const scaleY = cropSize / img.height;
        // 使用较小的缩放比例，确保图片完全显示在裁剪框内
        avatarScale.value = Math.min(scaleX, scaleY, 1.0);
        avatarOffsetX.value = 0;
        avatarOffsetY.value = 0;
      };
      img.src = e.target.result;
    };
    reader.readAsDataURL(file);
  }
};

const handleAvatarZoom = (delta) => {
  // 允许用户自由缩放，最小0.1，最大3.0（允许放大）
  const newScale = Math.max(0.1, Math.min(3.0, avatarScale.value + delta));
  avatarScale.value = newScale;
};

const handleAvatarDragStart = (event) => {
  event.preventDefault();
  isDragging.value = true;
  dragStartX.value = event.clientX - avatarOffsetX.value;
  dragStartY.value = event.clientY - avatarOffsetY.value;
};

const handleAvatarDrag = (event) => {
  if (!isDragging.value) return;
  event.preventDefault();
  avatarOffsetX.value = event.clientX - dragStartX.value;
  avatarOffsetY.value = event.clientY - dragStartY.value;
};

const handleAvatarDragEnd = () => {
  isDragging.value = false;
};

const cropAvatar = () => {
  // 创建canvas进行裁剪
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d');
  const size = 200; // 最终头像尺寸（正方形）
  canvas.width = size;
  canvas.height = size;

  const img = new Image();
  img.onload = () => {
    // 计算裁剪区域（以图片中心为基准，圆形裁剪框）
    const minDimension = Math.min(img.width, img.height);
    const sourceSize = minDimension * avatarScale.value;
    const centerX = img.width / 2;
    const centerY = img.height / 2;
    
    // 计算偏移（考虑缩放）
    const offsetX = avatarOffsetX.value / avatarScale.value;
    const offsetY = avatarOffsetY.value / avatarScale.value;
    
    const sourceX = centerX - sourceSize / 2 - offsetX;
    const sourceY = centerY - sourceSize / 2 - offsetY;

    // 创建圆形裁剪路径
    ctx.beginPath();
    ctx.arc(size / 2, size / 2, size / 2, 0, Math.PI * 2);
    ctx.clip();

    // 绘制裁剪后的头像
    ctx.drawImage(
      img,
      Math.max(0, sourceX), Math.max(0, sourceY), 
      Math.min(sourceSize, img.width - Math.max(0, sourceX)), 
      Math.min(sourceSize, img.height - Math.max(0, sourceY)),
      0, 0, size, size
    );

    // 转换为blob并上传
    canvas.toBlob((blob) => {
      const croppedFile = new File([blob], 'avatar.jpg', { type: 'image/jpeg' });
      uploadCroppedAvatar(croppedFile);
    }, 'image/jpeg', 0.9);
  };
  img.src = newAvatarPreview.value;
};

const uploadCroppedAvatar = async (croppedFile) => {
  changeAvatarError.value = '';
  changeAvatarSuccess.value = '';

  // 确认更换
  if (!confirm('确定要更换头像吗？')) {
    return;
  }

  try {
    const formData = new FormData();
    formData.append('avatar', croppedFile);

    const response = await fetch('/api/auth/change-avatar', {
      method: 'POST',
      headers: {
        'X-User-Id': userInfo.value.id.toString()
      },
      body: formData
    });

    const result = await response.json();

    if (result.success) {
      changeAvatarSuccess.value = '头像更换成功';
      // 更新用户信息
      userInfo.value.avatar_path = result.avatar_path;
      localStorage.setItem('userInfo', JSON.stringify(userInfo.value));
      // 重置状态
      showAvatarCrop.value = false;
      showAvatarUpload.value = false;
      newAvatarFile.value = null;
      newAvatarPreview.value = null;
      // 2秒后清空成功消息
      setTimeout(() => {
        changeAvatarSuccess.value = '';
      }, 2000);
    } else {
      changeAvatarError.value = result.message || '头像更换失败';
    }
  } catch (error) {
    console.error('更换头像失败:', error);
    changeAvatarError.value = '网络错误，请稍后重试';
  }
};

const handleConfirmAvatarUpload = () => {
  // 如果显示了裁剪界面，先进行裁剪
  if (showAvatarCrop.value) {
    cropAvatar();
  }
};

const handleUseDefaultAvatar = async () => {
  // 确认更换
  if (!confirm('确定要使用默认头像吗？')) {
    return;
  }

  changeAvatarError.value = '';
  changeAvatarSuccess.value = '';

  try {
    // 加载默认头像并压缩
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = async () => {
      // 创建canvas进行压缩
      const canvas = document.createElement('canvas');
      const ctx = canvas.getContext('2d');
      const size = 200; // 最终头像尺寸（正方形）
      canvas.width = size;
      canvas.height = size;

      // 计算缩放比例，保持宽高比
      const scale = Math.min(size / img.width, size / img.height);
      const scaledWidth = img.width * scale;
      const scaledHeight = img.height * scale;
      const x = (size - scaledWidth) / 2;
      const y = (size - scaledHeight) / 2;

      // 创建圆形裁剪路径
      ctx.beginPath();
      ctx.arc(size / 2, size / 2, size / 2, 0, Math.PI * 2);
      ctx.clip();

      // 绘制压缩后的头像
      ctx.drawImage(img, x, y, scaledWidth, scaledHeight);

      // 转换为blob并上传
      canvas.toBlob(async (blob) => {
        const compressedFile = new File([blob], 'default_avatar.jpg', { type: 'image/jpeg' });
        
        const formData = new FormData();
        formData.append('avatar', compressedFile);

        try {
          const response = await fetch('/api/auth/change-avatar', {
            method: 'POST',
            headers: {
              'X-User-Id': userInfo.value.id.toString()
            },
            body: formData
          });

          const result = await response.json();

          if (result.success) {
            changeAvatarSuccess.value = '已切换为默认头像';
            // 更新用户信息
            userInfo.value.avatar_path = result.avatar_path || '/default.jpg';
            localStorage.setItem('userInfo', JSON.stringify(userInfo.value));
            // 2秒后清空成功消息
            setTimeout(() => {
              changeAvatarSuccess.value = '';
            }, 2000);
          } else {
            changeAvatarError.value = result.message || '切换默认头像失败';
          }
        } catch (error) {
          console.error('切换默认头像失败:', error);
          changeAvatarError.value = '网络错误，请稍后重试';
        }
      }, 'image/jpeg', 0.9);
    };
    img.onerror = () => {
      changeAvatarError.value = '加载默认头像失败';
    };
    img.src = '/default.jpg';
  } catch (error) {
    console.error('切换默认头像失败:', error);
    changeAvatarError.value = '网络错误，请稍后重试';
  }
};

const handleChangePassword = async () => {
  changePasswordError.value = '';
  
  // 验证字段
  if (useSecurityQuestionForPassword.value) {
    if (!currentSecurityQuestion.value) {
      changePasswordError.value = '您尚未设置二级问题，无法使用此方式';
      return;
    }
    if (!securityAnswerForPassword.value || !newPassword.value || !confirmNewPassword.value) {
      changePasswordError.value = '请填写所有字段';
      return;
    }
  } else {
    if (!oldPassword.value || !newPassword.value || !confirmNewPassword.value) {
      changePasswordError.value = '请填写所有字段';
      return;
    }
  }
  
  if (newPassword.value.length < 6) {
    changePasswordError.value = '新密码至少需要6个字符';
    return;
  }
  
  if (newPassword.value !== confirmNewPassword.value) {
    changePasswordError.value = '两次输入的密码不一致';
    return;
  }
  
  try {
    let response;
    
    if (useSecurityQuestionForPassword.value) {
      // 先验证二级密码答案
      const verifyResponse = await fetch('/api/auth/verify-security-answer', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-Id': userInfo.value.id.toString()
        },
        body: JSON.stringify({
          answer: securityAnswerForPassword.value
        })
      });
      
      const verifyResult = await verifyResponse.json();
      
      if (!verifyResult.success) {
        changePasswordError.value = verifyResult.message || '二级密码答案错误';
        return;
      }
      
      // 验证通过后，获取原密码进行对比
      // 由于无法直接获取原密码，我们需要通过API来检查
      // 先尝试用新密码登录来验证是否与原密码相同（但这样不安全）
      // 更好的方式是后端API直接检查
      response = await fetch('/api/auth/change-password-by-security', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-Id': userInfo.value.id.toString()
        },
        body: JSON.stringify({
          security_answer: securityAnswerForPassword.value,
          new_password: newPassword.value
        })
      });
    } else {
      // 检查新密码是否与原密码相同
      if (oldPassword.value === newPassword.value) {
        changePasswordError.value = '新密码不能与原密码相同';
        return;
      }
      
      response = await fetch('/api/auth/change-password', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-Id': userInfo.value.id.toString()
        },
        body: JSON.stringify({
          old_password: oldPassword.value,
          new_password: newPassword.value
        })
      });
    }
    
    const result = await response.json();
    
    if (result.success) {
      changePasswordSuccess.value = '密码修改成功，即将退出登录';
      oldPassword.value = '';
      newPassword.value = '';
      confirmNewPassword.value = '';
      securityAnswerForPassword.value = '';
      useSecurityQuestionForPassword.value = false;
      // 直接退出登录，不询问
      setTimeout(() => {
        changePasswordSuccess.value = '';
        handleLogout(true);
      }, 1000);
    } else {
      changePasswordError.value = result.message || '修改密码失败';
    }
  } catch (error) {
    console.error('修改密码失败:', error);
    changePasswordError.value = '网络错误，请稍后重试';
  }
};

const loadSecurityQuestion = async () => {
  if (!userInfo.value || !userInfo.value.id) {
    return;
  }
  
  try {
    const response = await fetch(`/api/auth/user?user_id=${userInfo.value.id}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json'
      }
    });
    
    const result = await response.json();
    
    if (result.success && result.user_info) {
      currentSecurityQuestion.value = result.user_info.security_question || '';
    } else {
      currentSecurityQuestion.value = '';
    }
  } catch (error) {
    console.error('加载安全问题失败:', error);
    currentSecurityQuestion.value = '';
  }
};

const handlePasswordTabClick = () => {
  settingsTab.value = 'password';
  // 重置状态
  oldPassword.value = '';
  newPassword.value = '';
  confirmNewPassword.value = '';
  changePasswordError.value = '';
  changePasswordSuccess.value = '';
  useSecurityQuestionForPassword.value = false;
  securityAnswerForPassword.value = '';
  // 加载安全问题（用于二级密码验证）
  loadSecurityQuestion();
};

const handleSecurityTabClick = () => {
  settingsTab.value = 'security';
  // 重置状态
  securityAnswerVerified.value = false;
  oldSecurityAnswer.value = '';
  newSecurityQuestion.value = '';
  newSecurityAnswer.value = '';
  securityVerifyError.value = '';
  changeSecurityError.value = '';
  changeSecuritySuccess.value = '';
  // 加载安全问题
  loadSecurityQuestion();
};

const handleVerifySecurityAnswer = async () => {
  if (!oldSecurityAnswer.value) {
    securityVerifyError.value = '请输入原问题的答案';
    return;
  }

  securityVerifyError.value = '';

  try {
    const response = await fetch('/api/auth/verify-security-answer', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-User-Id': userInfo.value.id.toString()
      },
      body: JSON.stringify({
        answer: oldSecurityAnswer.value
      })
    });

    const result = await response.json();

    if (result.success) {
      securityAnswerVerified.value = true;
      securityVerifyError.value = '';
    } else {
      securityVerifyError.value = result.message || '答案错误';
    }
  } catch (error) {
    console.error('验证答案失败:', error);
    securityVerifyError.value = '网络错误，请稍后重试';
  }
};

const handleChangeSecurityQuestion = async () => {
  if (!newSecurityQuestion.value || !newSecurityAnswer.value) {
    changeSecurityError.value = '请填写新问题和新答案';
    return;
  }

  changeSecurityError.value = '';
  changeSecuritySuccess.value = '';

  try {
    const response = await fetch('/api/auth/change-security-question', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-User-Id': userInfo.value.id.toString()
      },
      body: JSON.stringify({
        question: newSecurityQuestion.value,
        answer: newSecurityAnswer.value
      })
    });

    const result = await response.json();

    if (result.success) {
      changeSecuritySuccess.value = currentSecurityQuestion.value ? '二级问题更换成功' : '二级问题设置成功';
      currentSecurityQuestion.value = newSecurityQuestion.value;
      // 重置状态
      securityAnswerVerified.value = false;
      oldSecurityAnswer.value = '';
      newSecurityQuestion.value = '';
      newSecurityAnswer.value = '';
      // 2秒后关闭对话框
      setTimeout(() => {
        showSettingsModal.value = false;
        changeSecuritySuccess.value = '';
      }, 2000);
    } else {
      changeSecurityError.value = result.message || '操作失败';
    }
  } catch (error) {
    console.error('更换二级问题失败:', error);
    changeSecurityError.value = '网络错误，请稍后重试';
  }
};

const handleLogout = (skipConfirm = false) => {
  // 退出登录
  if (skipConfirm || confirm('确定要退出登录吗？')) {
    userInfo.value = null;
    localStorage.removeItem('userInfo');
    showSettingsModal.value = false;
    router.push('/login');
  }
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

/* 右侧按钮 */
.right-actions { display: flex; align-items: center; gap: 20px; }
.text-link { font-size: 14px; color: #666; text-decoration: none; }
.text-link.router-link-active { font-weight: 600; color: #409eff; }
.text-link:hover { color: #333; }

/* 用户头像和昵称 */
.user-profile {
  position: relative;
  cursor: pointer;
  padding: 8px 12px;
  border-radius: 8px;
  transition: background 0.3s;
}

.user-profile:hover {
  background: #f5f7fa;
}

.user-profile-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}

.user-avatar-container {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  overflow: hidden;
  border: 2px solid #e4e7ed;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  transition: transform 0.3s;
}

.user-profile:hover .user-avatar-container {
  transform: scale(1.05);
}

.user-avatar {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.user-nickname {
  font-size: 12px;
  color: #666;
  font-weight: 400;
  text-align: center;
  max-width: 80px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 设置菜单 */
.settings-menu {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 8px;
  background: white;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  min-width: 150px;
  z-index: 1000;
}

.menu-item {
  padding: 10px 16px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: #333;
  transition: background 0.2s;
}

.menu-item:hover {
  background: #f5f7fa;
}

.menu-item:first-child {
  border-top-left-radius: 6px;
  border-top-right-radius: 6px;
}

.menu-item:last-child {
  border-bottom-left-radius: 6px;
  border-bottom-right-radius: 6px;
}

/* 修改密码对话框 */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
}

.modal-content {
  background: white;
  padding: 30px;
  border-radius: 8px;
  width: 400px;
  max-width: 90%;
}

.modal-content h3 {
  margin: 0 0 20px 0;
  color: #333;
}

.modal-content .input-group {
  margin-bottom: 15px;
}

.modal-content .input-group label {
  display: block;
  margin-bottom: 6px;
  color: #333;
  font-weight: 500;
  font-size: 14px;
}

.modal-content .input-group input {
  width: 100%;
  padding: 8px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 14px;
  box-sizing: border-box;
}

.modal-content .input-group input:focus {
  border-color: #409eff;
  outline: none;
}

.modal-actions {
  display: flex;
  gap: 10px;
  margin-top: 20px;
}

.modal-actions .submit-btn {
  flex: 1;
  padding: 10px;
  background: #409eff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
}

.modal-actions .submit-btn:hover {
  background: #66b1ff;
}

.modal-actions .cancel-btn {
  flex: 1;
  padding: 10px;
  background: #f0f2f5;
  color: #666;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
}

.modal-actions .cancel-btn:hover {
  background: #e4e7ed;
}

.success-message {
  color: #67c23a;
  font-size: 12px;
  margin-top: 8px;
}

.avatar-options {
  display: flex;
  gap: 12px;
  margin-top: 8px;
}

.option-btn {
  flex: 1;
  padding: 12px 20px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  background: white;
  cursor: pointer;
  transition: all 0.3s;
  font-size: 14px;
}

.option-btn:hover {
  border-color: #409eff;
  color: #409eff;
  background: #ecf5ff;
}

.avatar-preview-large {
  width: 150px;
  height: 150px;
  object-fit: cover;
  border-radius: 8px;
  margin-top: 12px;
  border: 2px solid #e4e7ed;
}

.error-message {
  margin-top: 10px;
  padding: 8px;
  background: #fee;
  color: #c33;
  border-radius: 4px;
  font-size: 13px;
}

main { 
  min-height: calc(100vh - 60px);
  width: 100%;
  position: relative;
}

.settings-link {
  font-size: 14px;
  color: #666;
  cursor: pointer;
  padding: 8px 12px;
  border-radius: 4px;
  transition: all 0.3s;
  display: flex;
  align-items: center;
  gap: 4px;
}

.settings-link:hover {
  background: #f5f7fa;
  color: #409eff;
}

.settings-modal {
  width: 500px;
  max-width: 90%;
}

.settings-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 20px;
  border-bottom: 1px solid #e4e7ed;
  flex-wrap: wrap;
}

.tab-item {
  padding: 10px 16px;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: all 0.3s;
  font-size: 14px;
  color: #666;
}

.tab-item:hover {
  color: #409eff;
}

.tab-item.active {
  color: #409eff;
  border-bottom-color: #409eff;
  font-weight: 500;
}

.tab-item.logout-item {
  margin-left: auto;
  color: #f56c6c;
}

.tab-item.logout-item:hover {
  color: #f56c6c;
  background: #fef0f0;
}

.settings-panel {
  min-height: 200px;
}

.security-question-display {
  padding: 8px 12px;
  background: #f5f7fa;
  border-radius: 4px;
  margin-bottom: 12px;
  font-size: 14px;
  color: #333;
}

.avatar-crop-container {
  margin-top: 16px;
}

.avatar-crop-frame {
  position: relative;
  width: 200px;
  height: 200px;
  margin: 0 auto;
  border: 3px solid #409eff;
  border-radius: 50%;
  overflow: hidden;
  background: #f5f7fa;
}

.avatar-crop-image-wrapper {
  width: 100%;
  height: 100%;
  position: relative;
  overflow: hidden;
}

.avatar-crop-image {
  position: absolute;
  top: 50%;
  left: 50%;
  transform-origin: center center;
  max-width: none;
  max-height: none;
  user-select: none;
  width: auto;
  height: auto;
}

.avatar-crop-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  border-radius: 50%;
  box-shadow: inset 0 0 0 3px rgba(64, 158, 255, 0.3);
  pointer-events: none;
}

.avatar-crop-controls {
  margin-top: 16px;
  text-align: center;
}

.avatar-crop-controls button {
  padding: 6px 16px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  background: white;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.3s;
}

.avatar-crop-controls button:hover:not(:disabled) {
  border-color: #409eff;
  color: #409eff;
}

.avatar-crop-controls button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
