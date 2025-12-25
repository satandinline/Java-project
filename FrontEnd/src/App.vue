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
          <router-link to="/aigc" class="text-link" style="font-weight: 600; color: #409eff;">AIGC</router-link>
          <router-link to="/multimodal" class="text-link">图文互搜</router-link>
          <router-link to="/upload" class="text-link">用户上传</router-link>
          <router-link to="/annotation" class="text-link">标注任务</router-link>
          
          <!-- 设置入口 -->
          <div class="settings-link" @click="handleSettingsClick">
            <span>⚙️</span> 设置
          </div>
          
          <!-- 数据大屏入口（仅管理员可见） -->
          <router-link v-if="isAdmin" to="/dashboard" class="text-link dashboard-link">
            📊 数据大屏
          </router-link>
          
          <!-- 用户管理入口（仅超级管理员可见） -->
          <router-link v-if="isSuperAdmin" to="/users" class="text-link users-link">
            👥 用户管理
          </router-link>
          
          <!-- 消息通知铃铛图标 -->
          <div class="notification-bell" @click="showNotificationList = !showNotificationList" v-if="isLoggedIn">
            <span class="bell-icon">🔔</span>
            <span v-if="unreadCount > 0" class="notification-badge">{{ unreadCount > 99 ? '99+' : unreadCount }}</span>
          </div>
          
          <!-- 通知列表下拉菜单 -->
          <div v-if="showNotificationList && isLoggedIn" class="notification-dropdown">
            <div class="notification-header">
              <span>消息通知</span>
              <button @click="markAllAsRead" class="mark-all-read-btn" v-if="unreadCount > 0">全部已读</button>
            </div>
            <div class="notification-list">
              <div v-if="notifications.length === 0" class="no-notifications">暂无通知</div>
              <div 
                v-for="notif in notifications" 
                :key="notif.id"
                class="notification-item"
                :class="{ unread: !notif.is_read }"
                @click="handleNotificationClick(notif)"
              >
                <div class="notification-content">{{ notif.content }}</div>
                <div class="notification-time">{{ formatNotificationTime(notif.created_at) }}</div>
              </div>
            </div>
          </div>
          
          <!-- 用户头像和昵称 -->
          <div class="user-profile">
            <div class="user-profile-content">
              <div class="user-avatar-container" @click="handleAvatarClick" style="cursor: pointer;">
                <img :src="getAvatarUrl(userInfo?.avatar_path)" class="user-avatar" alt="头像" @error="handleAvatarError" />
              </div>
              <div class="user-info">
                <div class="user-nickname">{{ userInfo?.nickname || userInfo?.account || '用户' }}</div>
              </div>
            </div>
          </div>
        </div>
        
        <!-- 设置对话框 -->
        <div v-if="showSettingsModal" class="modal-overlay" @click="fromAvatarClick ? closeSettingsModal() : (showSettingsModal = false)">
          <div class="modal-content settings-modal" @click.stop>
            <!-- 如果点击头像进入，只显示更换头像功能（不显示设置列表） -->
            <!-- 否则显示完整的设置列表 -->
            <div v-if="settingsTab === '' && !fromAvatarClick">
              <div class="modal-header">
                <h3>设置</h3>
                <button class="close-btn" @click="showSettingsModal = false">×</button>
              </div>
              
              <!-- 设置列表（美化后的样式） -->
              <div class="settings-list">
                <!-- 账号（仅显示） -->
                <div class="settings-item readonly">
                  <div class="settings-item-content">
                    <span class="settings-item-label">账号</span>
                    <span class="settings-item-value">{{ userInfo?.account || '未知' }}</span>
                  </div>
                </div>
                
                <!-- 昵称（可点击修改） -->
                <div class="settings-item clickable" @click="handleNicknameClick">
                  <div class="settings-item-content">
                    <div class="settings-item-main">
                      <span class="settings-item-label">昵称</span>
                      <span class="settings-item-arrow">›</span>
                    </div>
                    <div class="settings-item-sub">{{ userInfo?.nickname || '未设置' }}</div>
                  </div>
                </div>
                
                <!-- 个人签名（可点击设置） -->
                <div class="settings-item clickable" @click="handleSignatureClick">
                  <div class="settings-item-content">
                    <div class="settings-item-main">
                      <span class="settings-item-label">个人签名</span>
                      <span class="settings-item-arrow">›</span>
                    </div>
                    <div class="settings-item-sub">{{ (userInfo?.signature && userInfo.signature.trim()) || '未设置' }}</div>
                  </div>
                </div>
                
                <!-- 修改密码（可点击） -->
                <div class="settings-item clickable" @click="handlePasswordClick">
                  <div class="settings-item-content">
                    <div class="settings-item-main">
                      <span class="settings-item-label">修改密码</span>
                      <span class="settings-item-arrow">›</span>
                    </div>
                  </div>
                </div>
                
                <!-- 更换二级问题（可点击） -->
                <div class="settings-item clickable" @click="handleSecurityClick">
                  <div class="settings-item-content">
                    <div class="settings-item-main">
                      <span class="settings-item-label">更换二级问题</span>
                      <span class="settings-item-arrow">›</span>
                    </div>
                  </div>
                </div>
                
                <!-- 退出登录 -->
                <div class="settings-item clickable logout-item" @click="handleLogout">
                  <div class="settings-item-content">
                    <span class="settings-item-label">退出登录</span>
                  </div>
                </div>
                
                <!-- 注销账号 -->
                <div class="settings-item clickable delete-item" @click="handleDeleteAccountClick">
                  <div class="settings-item-content">
                    <span class="settings-item-label">注销账号</span>
                  </div>
                </div>
              </div>
            </div>
            
            <!-- 修改昵称面板 -->
            <div v-if="settingsTab === 'nickname'" class="settings-panel">
              <div class="modal-header">
                <h3>修改昵称</h3>
                <button class="close-btn" @click="settingsTab = ''">×</button>
              </div>
              <div class="input-group">
                <label>新昵称</label>
                <input type="text" v-model="newNickname" :placeholder="`当前昵称：${userInfo?.nickname || '未设置'}`" maxlength="100" />
              </div>
              <div v-if="changeNicknameError" class="error-message">
                {{ changeNicknameError }}
              </div>
              <div v-if="changeNicknameSuccess" class="success-message">
                {{ changeNicknameSuccess }}
              </div>
              <div class="modal-actions">
                <button @click="handleChangeNickname" class="submit-btn">确认修改</button>
                <button @click="settingsTab = ''" class="cancel-btn">返回</button>
              </div>
            </div>
            
            <!-- 个人签名面板 -->
            <div v-if="settingsTab === 'signature'" class="settings-panel">
              <div class="modal-header">
                <h3>个人签名</h3>
                <button class="close-btn" @click="settingsTab = ''">×</button>
              </div>
              <div class="input-group">
                <label>个人签名</label>
                <textarea v-model="newSignature" placeholder="请输入个人签名（最多500字）" maxlength="500" rows="4" style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; resize: vertical; font-family: inherit;"></textarea>
                <div style="text-align: right; color: #999; font-size: 12px; margin-top: 4px;">
                  {{ newSignature.length }}/500
                </div>
              </div>
              <div v-if="changeSignatureError" class="error-message">
                {{ changeSignatureError }}
              </div>
              <div v-if="changeSignatureSuccess" class="success-message">
                {{ changeSignatureSuccess }}
              </div>
              <div class="modal-actions">
                <button @click="handleChangeSignature" class="submit-btn">确认修改</button>
                <button @click="settingsTab = ''" class="cancel-btn">返回</button>
              </div>
            </div>
            
            <!-- 更换头像 -->
            <div v-if="settingsTab === 'avatar'" class="settings-panel">
              <div class="modal-header" v-if="!fromAvatarClick">
                <h3>更换头像</h3>
                <button class="close-btn" @click="settingsTab = ''">×</button>
              </div>
              <div class="modal-header" v-else>
                <h3>更换头像</h3>
                <button class="close-btn" @click="closeSettingsModal()">×</button>
              </div>
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
                <button @click="fromAvatarClick ? closeSettingsModal() : (settingsTab = '')" class="cancel-btn">返回</button>
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
                  <button @click="fromAvatarClick ? closeSettingsModal() : (settingsTab = '')" class="cancel-btn">返回</button>
                </div>
            </div>
            
            <!-- 更换二级问题 -->
            <div v-if="settingsTab === 'security'" class="settings-panel">
              <div class="modal-header">
                <h3>更换二级问题</h3>
                <button class="close-btn" @click="settingsTab = ''">×</button>
              </div>
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
                  <button @click="fromAvatarClick ? closeSettingsModal() : (settingsTab = '')" class="cancel-btn">返回</button>
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
                  <button @click="fromAvatarClick ? closeSettingsModal() : (settingsTab = '')" class="cancel-btn">返回</button>
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
                  <button @click="fromAvatarClick ? closeSettingsModal() : (settingsTab = '')" class="cancel-btn">返回</button>
                </div>
              </div>
            </div>
            
            <!-- 注销账号确认对话框 -->
            <div v-if="showDeleteAccountConfirm" class="settings-panel">
              <div class="input-group">
                <p style="color: #f56c6c; font-weight: bold; margin-bottom: 16px;">
                  警告：注销账号后将永久删除您的所有数据，此操作不可恢复！
                </p>
                <label>请输入密码确认</label>
                <input type="password" v-model="deleteAccountPassword" placeholder="请输入密码" style="ime-mode: disabled;" />
              </div>
              <div v-if="deleteAccountError" class="error-message">
                {{ deleteAccountError }}
              </div>
              <div class="modal-actions">
                <button @click="handleConfirmDeleteAccount" class="submit-btn" style="background: #f56c6c;">确认注销</button>
                <button @click="showDeleteAccountConfirm = false" class="cancel-btn">取消</button>
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
const settingsTab = ref(''); // '', 'nickname', 'signature', 'password', 'security', 'avatar'
const fromAvatarClick = ref(false); // 标记是否从头像点击进入

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

// 注销账号相关
const showDeleteAccountConfirm = ref(false);
const deleteAccountPassword = ref('');
const deleteAccountError = ref('');
const securityVerifyError = ref('');
const newSecurityQuestion = ref('');
const newSecurityAnswer = ref('');
const changeSecurityError = ref('');
const changeSecuritySuccess = ref('');

// 修改密码相关（使用二级密码）
const useSecurityQuestionForPassword = ref(false);
const securityAnswerForPassword = ref('');

// 修改昵称相关
const newNickname = ref('');
const changeNicknameError = ref('');
const changeNicknameSuccess = ref('');

// 修改个人签名相关
const newSignature = ref('');
const changeSignatureError = ref('');
const changeSignatureSuccess = ref('');

// 消息通知相关
const showNotificationList = ref(false);
const notifications = ref([]);
const unreadCount = ref(0);

// 加载通知列表
const loadNotifications = async () => {
  if (!userInfo.value || !userInfo.value.id) return;
  
  try {
    const response = await fetch(`/api/notifications?user_id=${userInfo.value.id}`);
    const data = await response.json();
    
    if (data.success) {
      notifications.value = data.notifications || [];
      unreadCount.value = notifications.value.filter(n => !n.is_read).length;
    }
  } catch (error) {
  }
};

// 标记全部已读
const markAllAsRead = async () => {
  if (!userInfo.value || !userInfo.value.id) return;
  
  try {
    const response = await fetch('/api/notifications/mark-all-read', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-User-Id': userInfo.value.id.toString()
      }
    });
    
    const data = await response.json();
    if (data.success) {
      unreadCount.value = 0;
      notifications.value.forEach(n => n.is_read = 1);
    }
  } catch (error) {
  }
};

// 处理通知点击
const handleNotificationClick = async (notif) => {
  // 标记为已读
  if (!notif.is_read) {
    try {
      await fetch(`/api/notifications/${notif.id}/read`, {
        method: 'POST'
      });
      notif.is_read = 1;
      unreadCount.value = Math.max(0, unreadCount.value - 1);
    } catch (error) {
    }
  }
  
  // 跳转到资源详情并定位到评论
  if (notif.related_id) {
    showNotificationList.value = false;
    // 根据通知类型跳转
    if (notif.notification_type === 'like' || notif.notification_type === 'reply') {
      // 需要先获取评论对应的resource_id
      try {
        const response = await fetch(`/api/comments/${notif.related_id}/resource-id`);
        const data = await response.json();
        if (data.success && data.resource_id) {
          router.push({
            path: '/resource/detail',
            query: {
              id: data.resource_id,
              comment_id: notif.related_id
            }
          });
        }
      } catch (error) {
      }
    }
  }
};

// 格式化通知时间
const formatNotificationTime = (timeStr) => {
  if (!timeStr) return '';
  const date = new Date(timeStr);
  const now = new Date();
  const diff = now - date;
  const minutes = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);
  
  if (minutes < 1) return '刚刚';
  if (minutes < 60) return `${minutes}分钟前`;
  if (hours < 24) return `${hours}小时前`;
  if (days < 7) return `${days}天前`;
  return date.toLocaleDateString('zh-CN');
};

onMounted(() => {
  // 从sessionStorage读取用户信息（sessionStorage在刷新后会清空，需要重新登录）
  // 注意：路由守卫已经处理了登录跳转，这里只负责更新组件状态，不进行路由跳转
  const savedUser = sessionStorage.getItem('userInfo');
  if (savedUser) {
    try {
      const parsedUser = JSON.parse(savedUser);
      // 验证用户信息是否有效（检查必要字段）
      if (!parsedUser || !parsedUser.id || !parsedUser.account) {
        sessionStorage.removeItem('userInfo');
        userInfo.value = null;
        // 路由守卫会处理跳转，这里不需要手动跳转
        return;
      }
      userInfo.value = parsedUser;
      // 加载通知列表
      loadNotifications();
      // 每30秒刷新一次通知
      setInterval(loadNotifications, 30000);
    } catch (e) {
      sessionStorage.removeItem('userInfo');
      userInfo.value = null;
      // 路由守卫会处理跳转，这里不需要手动跳转
    }
  } else {
    userInfo.value = null;
    // 路由守卫会处理跳转，这里不需要手动跳转
  }
});

const isLoggedIn = computed(() => !!userInfo.value);

// 检查是否为管理员（从数据库users表的role字段判断）
const isAdmin = computed(() => {
  return userInfo.value && (userInfo.value.role === '管理员' || userInfo.value.role === '超级管理员');
});

const isSuperAdmin = computed(() => {
  return userInfo.value && userInfo.value.role === '超级管理员';
});

  // 监听路由变化
router.afterEach(() => {
  // 从sessionStorage读取用户信息
  const savedUser = sessionStorage.getItem('userInfo');
  if (savedUser) {
    try {
      const parsedUser = JSON.parse(savedUser);
      if (parsedUser && parsedUser.id && parsedUser.account) {
        userInfo.value = parsedUser;
        // 加载通知列表
        loadNotifications();
      } else {
        userInfo.value = null;
      }
    } catch (e) {
      userInfo.value = null;
    }
  } else {
    userInfo.value = null;
  }
  
  // 如果用户信息不存在且不在登录页，跳转到登录页
  if (!userInfo.value && router.currentRoute.value.path !== '/login') {
    router.push('/login');
  }
});

const handleLoginSuccess = (userData) => {
  userInfo.value = userData || null;
  if (userInfo.value) {
    // 确保包含所有必要字段
    if (!userInfo.value.nickname) {
      userInfo.value.nickname = userInfo.value.account;
    }
    if (userInfo.value.signature === undefined) {
      userInfo.value.signature = null;
    }
    if (!userInfo.value.avatar_path || userInfo.value.avatar_path === './default.jpg') {
      userInfo.value.avatar_path = '/default.jpg';
    }
    // 保存到sessionStorage（Login.vue中已经保存，这里再次确认）
    sessionStorage.setItem('userInfo', JSON.stringify(userInfo.value));
    // 加载通知列表
    loadNotifications();
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
      // 如果是从头像点击进入的，2秒后关闭对话框；否则清空成功消息
      if (fromAvatarClick.value) {
        setTimeout(() => {
          changeAvatarSuccess.value = '';
          closeSettingsModal();
        }, 2000);
      } else {
        setTimeout(() => {
          changeAvatarSuccess.value = '';
        }, 2000);
      }
    } else {
      changeAvatarError.value = result.message || '头像更换失败';
    }
  } catch (error) {
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
            // 如果是从头像点击进入的，2秒后关闭对话框；否则清空成功消息
            if (fromAvatarClick.value) {
              setTimeout(() => {
                changeAvatarSuccess.value = '';
                closeSettingsModal();
              }, 2000);
            } else {
              setTimeout(() => {
                changeAvatarSuccess.value = '';
              }, 2000);
            }
          } else {
            changeAvatarError.value = result.message || '切换默认头像失败';
          }
        } catch (error) {
          changeAvatarError.value = '网络错误，请稍后重试';
        }
      }, 'image/jpeg', 0.9);
    };
    img.onerror = () => {
      changeAvatarError.value = '加载默认头像失败';
    };
    img.src = '/default.jpg';
  } catch (error) {
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
    changeSecurityError.value = '网络错误，请稍后重试';
  }
};

const handleChangeNickname = async () => {
  changeNicknameError.value = '';
  changeNicknameSuccess.value = '';
  
  if (!newNickname.value.trim()) {
    changeNicknameError.value = '请输入新昵称';
    return;
  }
  
  if (newNickname.value.trim().length > 100) {
    changeNicknameError.value = '昵称长度不能超过100个字符';
    return;
  }
  
  try {
    const response = await fetch('/api/auth/update-nickname', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-User-Id': userInfo.value.id.toString()
      },
      body: JSON.stringify({
        nickname: newNickname.value.trim()
      })
    });
    
    const result = await response.json();
    
    if (result.success) {
      changeNicknameSuccess.value = '昵称修改成功';
      // 更新用户信息
      if (result.user_info) {
        userInfo.value.nickname = result.user_info.nickname;
        localStorage.setItem('userInfo', JSON.stringify(userInfo.value));
      } else {
        userInfo.value.nickname = newNickname.value.trim();
        localStorage.setItem('userInfo', JSON.stringify(userInfo.value));
      }
      newNickname.value = '';
      // 2秒后返回设置列表
      setTimeout(() => {
        changeNicknameSuccess.value = '';
        settingsTab.value = '';
      }, 2000);
    } else {
      changeNicknameError.value = result.message || '修改昵称失败';
    }
  } catch (error) {
    changeNicknameError.value = '网络错误，请稍后重试';
  }
};

// 设置入口点击处理
const handleSettingsClick = () => {
  showSettingsModal.value = true;
  settingsTab.value = '';
  fromAvatarClick.value = false;
};

// 头像点击处理（只显示更换头像功能）
const handleAvatarClick = () => {
  showSettingsModal.value = true;
  settingsTab.value = 'avatar';
  fromAvatarClick.value = true;
  // 重置头像相关状态
  showAvatarUpload.value = false;
  showAvatarCrop.value = false;
  newAvatarFile.value = null;
  newAvatarPreview.value = null;
  changeAvatarError.value = '';
  changeAvatarSuccess.value = '';
};

// 关闭设置对话框
const closeSettingsModal = () => {
  showSettingsModal.value = false;
  settingsTab.value = '';
  fromAvatarClick.value = false;
  // 重置所有状态
  showAvatarUpload.value = false;
  showAvatarCrop.value = false;
  newAvatarFile.value = null;
  newAvatarPreview.value = null;
  changeAvatarError.value = '';
  changeAvatarSuccess.value = '';
};

// 昵称点击处理
const handleNicknameClick = () => {
  settingsTab.value = 'nickname';
  fromAvatarClick.value = false;
  newNickname.value = userInfo.value?.nickname || '';
  changeNicknameError.value = '';
  changeNicknameSuccess.value = '';
};

// 个人签名点击处理
const handleSignatureClick = () => {
  settingsTab.value = 'signature';
  fromAvatarClick.value = false;
  newSignature.value = userInfo.value?.signature || '';
  changeSignatureError.value = '';
  changeSignatureSuccess.value = '';
};

// 修改密码点击处理
const handlePasswordClick = () => {
  fromAvatarClick.value = false;
  handlePasswordTabClick();
};

// 更换二级问题点击处理
const handleSecurityClick = () => {
  fromAvatarClick.value = false;
  handleSecurityTabClick();
};

// 注销账号点击处理
const handleDeleteAccountClick = () => {
  showDeleteAccountConfirm.value = true;
  deleteAccountPassword.value = '';
  deleteAccountError.value = '';
};

// 修改个人签名
const handleChangeSignature = async () => {
  changeSignatureError.value = '';
  changeSignatureSuccess.value = '';
  
  if (newSignature.value.length > 500) {
    changeSignatureError.value = '个人签名长度不能超过500个字符';
    return;
  }
  
  try {
    const response = await fetch('/api/auth/update-signature', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-User-Id': userInfo.value.id.toString()
      },
      body: JSON.stringify({
        signature: newSignature.value.trim()
      })
    });
    
    const result = await response.json();
    
    if (result.success) {
      changeSignatureSuccess.value = '个人签名修改成功';
      // 更新用户信息
      if (result.user_info) {
        userInfo.value.signature = result.user_info.signature;
        localStorage.setItem('userInfo', JSON.stringify(userInfo.value));
      } else {
        userInfo.value.signature = newSignature.value.trim();
        localStorage.setItem('userInfo', JSON.stringify(userInfo.value));
      }
      // 2秒后返回设置列表
      setTimeout(() => {
        changeSignatureSuccess.value = '';
        settingsTab.value = '';
      }, 2000);
    } else {
      changeSignatureError.value = result.message || '修改个人签名失败';
    }
  } catch (error) {
    changeSignatureError.value = '网络错误，请稍后重试';
  }
};

// 确认注销账号
const handleConfirmDeleteAccount = async () => {
  deleteAccountError.value = '';
  
  if (!deleteAccountPassword.value) {
    deleteAccountError.value = '请输入密码确认';
    return;
  }
  
  if (!confirm('确定要注销账号吗？此操作不可恢复，将删除您的所有数据！')) {
    return;
  }
  
  try {
    const response = await fetch('/api/auth/delete-account', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-User-Id': userInfo.value.id.toString()
      },
      body: JSON.stringify({
        password: deleteAccountPassword.value
      })
    });
    
    const result = await response.json();
    
    if (result.success) {
      alert('账号已注销');
      // 退出登录
      userInfo.value = null;
      localStorage.removeItem('userInfo');
      showSettingsModal.value = false;
      router.push('/login');
    } else {
      deleteAccountError.value = result.message || '注销账号失败';
    }
  } catch (error) {
    deleteAccountError.value = '网络错误，请稍后重试';
  }
};

const handleLogout = async (skipConfirm = false) => {
  // 退出登录
  if (skipConfirm || confirm('确定要退出登录吗？')) {
    // 调用后端API更新在线状态
    if (userInfo.value && userInfo.value.id) {
      try {
        await fetch('/api/auth/logout', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            user_id: userInfo.value.id
          })
        });
      } catch (e) {
        // 即使失败也继续登出流程
      }
    }
    
    userInfo.value = null;
    sessionStorage.removeItem('userInfo');
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
  max-width: 1600px;
  margin: 0 auto;
  height: 80px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 30px;
}

.logo-text { font-weight: bold; font-size: 20px; color: #333; }

/* 右侧按钮 */
.right-actions { display: flex; align-items: center; gap: 24px; }
.text-link { font-size: 18px; font-weight: 600; color: #666; text-decoration: none; padding: 8px 12px; }
.text-link.router-link-active { font-weight: 700; color: #409eff; }
.text-link:hover { color: #333; }

/* 用户头像和昵称 */
.user-profile {
  position: relative;
  cursor: pointer;
  padding: 10px 16px;
  border-radius: 8px;
  transition: background 0.3s;
  min-width: 100px;
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

.user-info {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.user-nickname {
  font-size: 14px;
  color: #666;
  font-weight: 500;
  text-align: center;
  max-width: 100px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-account {
  font-size: 10px;
  color: #999;
  text-align: center;
  max-width: 80px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: help;
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
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.12);
  background: #fff;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 16px;
  margin-bottom: 20px;
  border-bottom: 1px solid #e4e7ed;
}

.modal-header h3 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #303133;
}

.close-btn {
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  font-size: 24px;
  color: #909399;
  cursor: pointer;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.3s;
  line-height: 1;
  padding: 0;
}

.close-btn:hover {
  background: #f5f7fa;
  color: #606266;
}

/* 设置列表样式（美化后） */
.settings-list {
  display: flex;
  flex-direction: column;
  gap: 0;
  background: #fff;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid #e4e7ed;
}

.settings-item {
  padding: 16px 20px;
  border-bottom: 1px solid #f0f2f5;
  transition: all 0.3s;
  background: #fff;
}

.settings-item:last-child {
  border-bottom: none;
}

.settings-item.clickable {
  cursor: pointer;
}

.settings-item.clickable:hover {
  background: #f5f7fa;
}

.settings-item.readonly {
  cursor: default;
  background: #fafafa;
}

.settings-item-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.settings-item-main {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.settings-item-label {
  font-size: 15px;
  color: #303133;
  font-weight: 500;
}

.settings-item-sub {
  font-size: 13px;
  color: #909399;
  margin-top: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  padding-left: 0;
}

.settings-item-value {
  font-size: 14px;
  color: #606266;
  font-weight: 400;
}

.settings-item-arrow {
  font-size: 20px;
  color: #c0c4cc;
  font-weight: 300;
  transition: all 0.3s;
}

.settings-item.clickable:hover .settings-item-arrow {
  color: #409eff;
  transform: translateX(2px);
}

.settings-item.logout-item,
.settings-item.delete-item {
  margin-top: 8px;
  border-top: 1px solid #e4e7ed;
  border-radius: 0 0 8px 8px;
}

.settings-item.logout-item .settings-item-label,
.settings-item.delete-item .settings-item-label {
  color: #f56c6c;
  font-weight: 500;
}

.settings-item.logout-item:hover,
.settings-item.delete-item:hover {
  background: #fef0f0;
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

/* 消息通知样式 */
.notification-bell {
  position: relative;
  cursor: pointer;
  padding: 8px 12px;
  font-size: 20px;
  transition: all 0.3s;
}

.notification-bell:hover {
  background: #f5f7fa;
  border-radius: 4px;
}

.notification-badge {
  position: absolute;
  top: 4px;
  right: 4px;
  background: #f56c6c;
  color: white;
  border-radius: 10px;
  padding: 2px 6px;
  font-size: 12px;
  min-width: 18px;
  text-align: center;
  line-height: 14px;
}

.notification-dropdown {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 8px;
  background: white;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  width: 360px;
  max-height: 500px;
  z-index: 2000;
  display: flex;
  flex-direction: column;
}

.notification-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid #e4e7ed;
  font-weight: 600;
}

.mark-all-read-btn {
  padding: 4px 12px;
  background: #409eff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
}

.mark-all-read-btn:hover {
  background: #66b1ff;
}

.notification-list {
  flex: 1;
  overflow-y: auto;
  max-height: 400px;
}

.no-notifications {
  padding: 40px;
  text-align: center;
  color: #999;
}

.notification-item {
  padding: 12px 16px;
  border-bottom: 1px solid #f0f0f0;
  cursor: pointer;
  transition: background 0.2s;
}

.notification-item:hover {
  background: #f5f7fa;
}

.notification-item.unread {
  background: #ecf5ff;
}

.notification-content {
  font-size: 14px;
  color: #333;
  margin-bottom: 4px;
}

.notification-time {
  font-size: 12px;
  color: #999;
}
</style>
