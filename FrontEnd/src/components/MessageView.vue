<template>
  <div class="message-view">
    <div class="message-header">
      <h2>消息通知</h2>
      <button v-if="unreadCount > 0" @click="markAllAsRead" class="mark-all-read-btn">
        全部标记为已读
      </button>
    </div>
    
    <div class="message-list">
      <div v-if="messages.length === 0" class="no-messages">
        暂无消息
      </div>
      
      <div 
        v-for="message in messages" 
        :key="message.id"
        class="message-item"
        :class="{ unread: !message.is_read }"
        @click="handleMessageClick(message)"
      >
        <div class="message-icon">
          <span v-if="message.notification_type === 'like'">👍</span>
          <span v-else-if="message.notification_type === 'reply'">💬</span>
          <span v-else>🔔</span>
        </div>
        <div class="message-content">
          <div class="message-text">{{ message.content }}</div>
          <div class="message-time">{{ formatTime(message.created_at) }}</div>
        </div>
        <div v-if="!message.is_read" class="unread-dot"></div>
      </div>
    </div>
    
    <!-- 分页 -->
    <div class="pagination" v-if="totalPages > 1">
      <button 
        @click="goToPage(currentPage - 1)" 
        :disabled="currentPage === 1"
        class="page-btn"
      >
        上一页
      </button>
      <span class="page-info">
        第 {{ currentPage }} / {{ totalPages }} 页（共 {{ total }} 条）
      </span>
      <button 
        @click="goToPage(currentPage + 1)" 
        :disabled="currentPage >= totalPages"
        class="page-btn"
      >
        下一页
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';

const router = useRouter();

const messages = ref([]);
const currentPage = ref(1);
const pageSize = ref(20);
const total = ref(0);
const totalPages = ref(0);
const unreadCount = ref(0);

// 加载消息列表
const loadMessages = async (page = 1) => {
  try {
    const userInfo = JSON.parse(localStorage.getItem('userInfo') || sessionStorage.getItem('userInfo') || '{}');
    if (!userInfo || !userInfo.id) {
      return;
    }
    
    const response = await fetch(`/api/notifications?user_id=${userInfo.id}&page=${page}&page_size=${pageSize.value}`);
    const data = await response.json();
    
    if (data.success) {
      messages.value = data.notifications || [];
      total.value = data.total || 0;
      totalPages.value = data.total_pages || 1;
      currentPage.value = data.page || page;
      unreadCount.value = data.unread_count || 0;
    }
  } catch (error) {
    console.error('加载消息失败:', error);
  }
};

// 处理消息点击
const handleMessageClick = async (message) => {
  // 标记为已读
  if (!message.is_read) {
    try {
      const userInfo = JSON.parse(localStorage.getItem('userInfo') || sessionStorage.getItem('userInfo') || '{}');
      await fetch(`/api/notifications/${message.id}/read`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-Id': userInfo.id.toString()
        }
      });
      message.is_read = 1;
      unreadCount.value = Math.max(0, unreadCount.value - 1);
    } catch (error) {
      console.error('标记已读失败:', error);
    }
  }
  
  // 跳转到对应的评论
  if (message.related_id) {
    // 获取评论对应的资源ID
    try {
      const userInfo = JSON.parse(localStorage.getItem('userInfo') || sessionStorage.getItem('userInfo') || '{}');
      const response = await fetch(`/api/comments/${message.related_id}`);
      const data = await response.json();
      
      if (data.success && data.comment) {
        const resourceId = data.comment.resource_id;
        // 跳转到资源详情页，并高亮对应的评论
        router.push({
          path: '/resource/detail',
          query: {
            resource_id: resourceId,
            highlight_comment_id: message.related_id
          }
        });
      } else {
        alert('评论不存在或已被删除');
      }
    } catch (error) {
      console.error('获取评论信息失败:', error);
      alert('无法跳转到对应评论');
    }
  }
};

// 全部标记为已读
const markAllAsRead = async () => {
  try {
    const userInfo = JSON.parse(localStorage.getItem('userInfo') || sessionStorage.getItem('userInfo') || '{}');
    const response = await fetch(`/api/notifications/mark-all-read`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-User-Id': userInfo.id.toString()
      }
    });
    
    const data = await response.json();
    if (data.success) {
      // 重新加载消息列表
      await loadMessages(currentPage.value);
    }
  } catch (error) {
    console.error('标记全部已读失败:', error);
  }
};

// 格式化时间
const formatTime = (timeStr) => {
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

// 分页
const goToPage = (page) => {
  if (page >= 1 && page <= totalPages.value) {
    loadMessages(page);
  }
};

onMounted(() => {
  loadMessages();
});
</script>

<style scoped>
.message-view {
  max-width: 800px;
  margin: 20px auto;
  padding: 20px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.message-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 15px;
  border-bottom: 1px solid #eee;
}

.message-header h2 {
  margin: 0;
  font-size: 24px;
  color: #333;
}

.mark-all-read-btn {
  padding: 8px 16px;
  background: #409eff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
}

.mark-all-read-btn:hover {
  background: #66b1ff;
}

.message-list {
  min-height: 400px;
}

.no-messages {
  text-align: center;
  padding: 60px 20px;
  color: #999;
  font-size: 16px;
}

.message-item {
  display: flex;
  align-items: flex-start;
  padding: 15px;
  margin-bottom: 10px;
  background: #f9f9f9;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.2s;
  position: relative;
}

.message-item:hover {
  background: #f0f0f0;
}

.message-item.unread {
  background: #e8f4ff;
  border-left: 3px solid #409eff;
}

.message-icon {
  font-size: 24px;
  margin-right: 12px;
  flex-shrink: 0;
}

.message-content {
  flex: 1;
}

.message-text {
  font-size: 15px;
  color: #333;
  margin-bottom: 6px;
  line-height: 1.5;
}

.message-time {
  font-size: 12px;
  color: #999;
}

.unread-dot {
  width: 8px;
  height: 8px;
  background: #409eff;
  border-radius: 50%;
  margin-left: 10px;
  flex-shrink: 0;
  margin-top: 8px;
}

.pagination {
  display: flex;
  justify-content: center;
  align-items: center;
  margin-top: 20px;
  gap: 15px;
}

.page-btn {
  padding: 8px 16px;
  border: 1px solid #ddd;
  border-radius: 4px;
  background-color: #fff;
  cursor: pointer;
  font-size: 14px;
}

.page-btn:hover:not(:disabled) {
  background-color: #f0f0f0;
}

.page-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.page-info {
  font-size: 14px;
  color: #666;
}
</style>

