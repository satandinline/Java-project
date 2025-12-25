<template>
  <div class="user-management-container">
    <div class="page-header">
      <h1>用户管理</h1>
      <button class="refresh-btn" @click="loadUsers">刷新</button>
    </div>

    <div v-if="loading" class="loading">加载中...</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else class="users-table">
      <table>
        <thead>
          <tr>
            <th>账号</th>
            <th>昵称</th>
            <th>角色</th>
            <th>状态</th>
            <th>最后活跃</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="user in users" :key="user.id" :class="{ 'online-user': user.is_online }">
            <td>{{ user.account }}</td>
            <td>{{ user.nickname || '未设置' }}</td>
            <td>
              <span :class="getRoleClass(user.role)">{{ user.role }}</span>
            </td>
            <td>
              <span :class="user.is_online ? 'status-online' : 'status-offline'">
                {{ user.is_online ? '在线' : '离线' }}
              </span>
            </td>
            <td>{{ formatTime(user.last_active_time) }}</td>
            <td>
              <div v-if="user.role !== '超级管理员'" class="action-buttons">
                <button 
                  v-if="user.role === '普通用户'"
                  class="btn-promote"
                  @click="openConfirmDialog(user.id, '管理员', user.account, user.nickname)"
                  :disabled="switching"
                >
                  设为管理员
                </button>
                <button 
                  v-if="user.role === '管理员'"
                  class="btn-demote"
                  @click="openConfirmDialog(user.id, '普通用户', user.account, user.nickname)"
                  :disabled="switching"
                >
                  设为普通用户
                </button>
              </div>
              <span v-else class="no-action">-</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    
    <!-- 确认对话框 -->
    <div v-if="showConfirmDialog" class="modal-overlay" @click="closeConfirmDialog">
      <div class="modal-content confirm-dialog" @click.stop>
        <div class="modal-header">
          <h3>确认切换用户身份</h3>
          <button class="close-btn" @click="closeConfirmDialog">×</button>
        </div>
        <div class="modal-body">
          <p>确定要将以下用户的身份切换为 <strong>"{{ confirmNewRole }}"</strong> 吗？</p>
          <div class="user-info-box">
            <p><strong>账号：</strong>{{ confirmUserAccount }}</p>
            <p><strong>昵称：</strong>{{ confirmUserNickname }}</p>
            <p><strong>新角色：</strong>{{ confirmNewRole }}</p>
          </div>
        </div>
        <div class="modal-actions">
          <button class="btn-cancel" @click="closeConfirmDialog">取消</button>
          <button class="btn-confirm" @click="switchRole" :disabled="switching">
            {{ switching ? '切换中...' : '确认切换' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';

const users = ref([]);
const loading = ref(false);
const error = ref('');
const switching = ref(false);

// 导入统一的getCurrentUser函数
import { getCurrentUser } from '../utils/api.js';

const loadUsers = async () => {
  loading.value = true;
  error.value = '';
  
  const currentUser = getCurrentUser();
  if (!currentUser || !currentUser.id) {
    error.value = '请先登录';
    loading.value = false;
    return;
  }

  try {
    const response = await fetch(`/api/auth/users?userId=${currentUser.id}`);
    
    if (!response.ok) {
      if (response.status === 403) {
        const errorData = await response.json().catch(() => ({}));
        error.value = errorData.message || '权限不足，仅超级管理员可访问';
      } else {
        error.value = `加载失败：HTTP ${response.status}`;
      }
      return;
    }
    
    const data = await response.json();
    
    if (data.success) {
      users.value = data.users || [];
    } else {
      error.value = data.message || '加载用户列表失败';
    }
  } catch (e) {
    error.value = '加载用户列表失败，请稍后重试';
  } finally {
    loading.value = false;
  }
};

const showConfirmDialog = ref(false);
const confirmTargetUserId = ref(null);
const confirmNewRole = ref('');
const confirmUserAccount = ref('');
const confirmUserNickname = ref('');

const openConfirmDialog = (targetUserId, newRole, userAccount, userNickname) => {
  confirmTargetUserId.value = targetUserId;
  confirmNewRole.value = newRole;
  confirmUserAccount.value = userAccount;
  confirmUserNickname.value = userNickname;
  showConfirmDialog.value = true;
};

const closeConfirmDialog = () => {
  showConfirmDialog.value = false;
  confirmTargetUserId.value = null;
  confirmNewRole.value = '';
  confirmUserAccount.value = '';
  confirmUserNickname.value = '';
};

const switchRole = async () => {
  if (!confirmTargetUserId.value || !confirmNewRole.value) {
    return;
  }

  switching.value = true;
  const currentUser = getCurrentUser();
  
  try {
    const response = await fetch('/api/auth/switch-role', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        current_user_id: currentUser.id,
        target_user_id: confirmTargetUserId.value,
        new_role: confirmNewRole.value
      })
    });
    
    const data = await response.json();
    
    if (data.success) {
      alert('用户身份切换成功');
      closeConfirmDialog();
      await loadUsers(); // 重新加载用户列表
    } else {
      alert(data.message || '切换失败');
    }
  } catch (e) {
    alert('切换失败，请稍后重试');
  } finally {
    switching.value = false;
  }
};

const getRoleClass = (role) => {
  if (role === '超级管理员') return 'role-super-admin';
  if (role === '管理员') return 'role-admin';
  return 'role-user';
};

const formatTime = (time) => {
  if (!time) return '-';
  const date = new Date(time);
  return date.toLocaleString('zh-CN');
};

onMounted(() => {
  loadUsers();
});
</script>

<style scoped>
.user-management-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 30px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 30px;
}

.page-header h1 {
  margin: 0;
  font-size: 24px;
  color: #333;
}

.refresh-btn {
  padding: 8px 16px;
  background: #409eff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
}

.refresh-btn:hover {
  background: #66b1ff;
}

.loading, .error {
  text-align: center;
  padding: 40px;
  font-size: 16px;
}

.error {
  color: #f56c6c;
}

.users-table {
  background: white;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

table {
  width: 100%;
  border-collapse: collapse;
}

thead {
  background: #f5f7fa;
}

th {
  padding: 12px 16px;
  text-align: left;
  font-weight: 600;
  color: #333;
  border-bottom: 2px solid #e4e7ed;
}

td {
  padding: 12px 16px;
  border-bottom: 1px solid #e4e7ed;
}

tr:hover {
  background: #f5f7fa;
}

.online-user {
  background: #f0f9ff;
}

.role-super-admin {
  color: #e6a23c;
  font-weight: 600;
}

.role-admin {
  color: #409eff;
  font-weight: 500;
}

.role-user {
  color: #909399;
}

.status-online {
  color: #67c23a;
  font-weight: 500;
}

.status-offline {
  color: #909399;
}

.action-buttons {
  display: flex;
  gap: 8px;
}

.btn-promote, .btn-demote {
  padding: 6px 12px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
  transition: all 0.3s;
}

.btn-promote {
  background: #409eff;
  color: white;
}

.btn-promote:hover:not(:disabled) {
  background: #66b1ff;
}

.btn-demote {
  background: #909399;
  color: white;
}

.btn-demote:hover:not(:disabled) {
  background: #a6a9ad;
}

.btn-promote:disabled, .btn-demote:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.no-action {
  color: #c0c4cc;
  font-style: italic;
}

/* 确认对话框样式 */
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
  z-index: 1000;
}

.modal-content {
  background: white;
  border-radius: 8px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
  min-width: 400px;
  max-width: 500px;
}

.confirm-dialog .modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  border-bottom: 1px solid #e4e7ed;
}

.confirm-dialog .modal-header h3 {
  margin: 0;
  font-size: 18px;
  color: #333;
}

.confirm-dialog .close-btn {
  background: none;
  border: none;
  font-size: 24px;
  color: #909399;
  cursor: pointer;
  padding: 0;
  width: 24px;
  height: 24px;
  line-height: 24px;
  transition: color 0.3s;
}

.confirm-dialog .close-btn:hover {
  color: #333;
}

.confirm-dialog .modal-body {
  padding: 24px;
}

.confirm-dialog .modal-body p {
  margin: 0 0 16px 0;
  color: #606266;
  font-size: 14px;
  line-height: 1.6;
}

.confirm-dialog .user-info-box {
  background: #f5f7fa;
  border-radius: 4px;
  padding: 16px;
  margin-top: 16px;
}

.confirm-dialog .user-info-box p {
  margin: 8px 0;
  color: #303133;
  font-size: 14px;
}

.confirm-dialog .user-info-box p:first-child {
  margin-top: 0;
}

.confirm-dialog .user-info-box p:last-child {
  margin-bottom: 0;
}

.confirm-dialog .modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 24px;
  border-top: 1px solid #e4e7ed;
}

.confirm-dialog .btn-cancel,
.confirm-dialog .btn-confirm {
  padding: 10px 20px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.3s;
}

.confirm-dialog .btn-cancel {
  background: #f5f7fa;
  color: #606266;
}

.confirm-dialog .btn-cancel:hover {
  background: #e4e7ed;
}

.confirm-dialog .btn-confirm {
  background: #409eff;
  color: white;
}

.confirm-dialog .btn-confirm:hover:not(:disabled) {
  background: #66b1ff;
}

.confirm-dialog .btn-confirm:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>

