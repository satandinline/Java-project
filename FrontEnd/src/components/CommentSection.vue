<template>
  <div class="comment-section">
    <div class="comment-header">
      <h3>评论 ({{ comments.length }})</h3>
      <button class="close-btn" @click="$emit('close')">×</button>
    </div>

    <!-- 评论输入框 -->
    <div class="comment-input-area">
      <textarea
        v-model="newComment"
        placeholder="写下你的评论..."
        class="comment-textarea"
        rows="3"
      ></textarea>
      <button 
        class="submit-btn" 
        @click="submitComment"
        :disabled="!newComment.trim() || isSubmitting"
      >
        {{ isSubmitting ? '发布中...' : '发布评论' }}
      </button>
    </div>

    <!-- 评论列表 -->
    <div class="comments-list">
      <div 
        v-for="comment in comments" 
        :key="comment.id"
        class="comment-item"
        :class="{ 'highlight-comment': highlightCommentId === comment.id }"
        :id="`comment-${comment.id}`"
      >
        <div class="comment-header-info">
          <img 
            :src="comment.avatar_path || '/default.jpg'" 
            :alt="comment.nickname || comment.account || '用户'"
            class="comment-avatar"
          />
          <div class="comment-user-info">
            <span class="comment-username">{{ comment.nickname || comment.account || '用户' }}</span>
            <span class="comment-time">{{ formatTime(comment.created_at) }}</span>
          </div>
        </div>
        <div class="comment-content">{{ comment.comment_content }}</div>
        <div class="comment-actions">
          <button 
            class="like-btn"
            :class="{ liked: isLiked(comment.id) }"
            @click="toggleLike(comment.id)"
          >
            👍 {{ comment.like_count || 0 }}
          </button>
          <button 
            class="reply-btn"
            @click="showReplyInput(comment.id)"
          >
            回复
          </button>
        </div>

        <!-- 回复输入框 -->
        <div v-if="replyingTo === comment.id" class="reply-input-area">
          <textarea
            v-model="newReply"
            placeholder="写下你的回复..."
            class="reply-textarea"
            rows="2"
          ></textarea>
          <div class="reply-actions">
            <button 
              class="submit-btn" 
              @click="submitReply(comment.id)"
              :disabled="!newReply.trim() || isSubmitting"
            >
              发送
            </button>
            <button 
              class="cancel-btn" 
              @click="cancelReply"
            >
              取消
            </button>
          </div>
        </div>

        <!-- 回复列表 -->
        <div v-if="comment.replies && comment.replies.length > 0" class="replies-list">
          <div 
            v-for="reply in comment.replies" 
            :key="reply.id"
            class="reply-item"
          >
            <img 
              :src="reply.avatar_path || '/default.jpg'" 
              :alt="reply.nickname || reply.account || '用户'"
              class="reply-avatar"
            />
            <div class="reply-content-wrapper">
              <div class="reply-user-info">
                <span class="reply-username">{{ reply.nickname || reply.account || '用户' }}</span>
                <span class="reply-time">{{ formatTime(reply.created_at) }}</span>
              </div>
              <div class="reply-content">{{ reply.reply_content }}</div>
            </div>
          </div>
        </div>
      </div>

      <div v-if="comments.length === 0" class="empty-comments">
        暂无评论，快来发表第一条评论吧！
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';

const props = defineProps({
  resourceId: {
    type: Number,
    required: true
  },
  userId: {
    type: Number,
    required: true
  },
  highlightCommentId: {
    type: Number,
    default: null
  }
});

const emit = defineEmits(['close']);

const comments = ref([]);
const newComment = ref('');
const newReply = ref('');
const replyingTo = ref(null);
const isSubmitting = ref(false);
const likedComments = ref(new Set());

// 加载评论列表
const loadComments = async () => {
  try {
    const response = await fetch(`/api/comments?resource_id=${props.resourceId}`);
    const data = await response.json();
    
    if (data.success) {
      comments.value = data.comments || [];
      // 初始化点赞状态（这里可以调用API获取用户已点赞的评论）
    }
  } catch (error) {
  }
};

// 发布评论
const submitComment = async () => {
  if (!newComment.value.trim()) return;
  
  isSubmitting.value = true;
  try {
    const response = await fetch('/api/comments', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        resource_id: props.resourceId,
        user_id: props.userId,
        comment_content: newComment.value.trim()
      })
    });
    
    const data = await response.json();
    if (data.success) {
      comments.value.unshift(data.comment);
      newComment.value = '';
    } else {
      alert(data.message || '发布评论失败');
    }
  } catch (error) {
    alert('发布评论失败，请重试');
  } finally {
    isSubmitting.value = false;
  }
};

// 点赞/取消点赞
const toggleLike = async (commentId) => {
  try {
    const response = await fetch(`/api/comments/${commentId}/like`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        user_id: props.userId
      })
    });
    
    const data = await response.json();
    if (data.success) {
      const comment = comments.value.find(c => c.id === commentId);
      if (comment) {
        comment.like_count = data.like_count;
        if (data.action === 'liked') {
          likedComments.value.add(commentId);
        } else {
          likedComments.value.delete(commentId);
        }
      }
    }
  } catch (error) {
  }
};

// 检查是否已点赞
const isLiked = (commentId) => {
  return likedComments.value.has(commentId);
};

// 显示回复输入框
const showReplyInput = (commentId) => {
  replyingTo.value = commentId;
  newReply.value = '';
};

// 取消回复
const cancelReply = () => {
  replyingTo.value = null;
  newReply.value = '';
};

// 提交回复
const submitReply = async (commentId) => {
  if (!newReply.value.trim()) return;
  
  isSubmitting.value = true;
  try {
    const response = await fetch(`/api/comments/${commentId}/reply`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        user_id: props.userId,
        reply_content: newReply.value.trim()
      })
    });
    
    const data = await response.json();
    if (data.success) {
      const comment = comments.value.find(c => c.id === commentId);
      if (comment) {
        if (!comment.replies) {
          comment.replies = [];
        }
        comment.replies.push(data.reply);
      }
      cancelReply();
    } else {
      alert(data.message || '回复失败');
    }
  } catch (error) {
    alert('回复失败，请重试');
  } finally {
    isSubmitting.value = false;
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

// 滚动到指定评论
const scrollToComment = (commentId) => {
  const commentElement = document.getElementById(`comment-${commentId}`);
  if (commentElement) {
    commentElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
    // 添加高亮效果
    commentElement.classList.add('highlight-comment');
    setTimeout(() => {
      commentElement.classList.remove('highlight-comment');
    }, 3000);
  }
};

// 暴露方法给父组件
defineExpose({
  scrollToComment
});

onMounted(() => {
  loadComments();
  
  // 如果有高亮评论ID，加载后滚动到该评论
  if (props.highlightCommentId) {
    setTimeout(() => {
      scrollToComment(props.highlightCommentId);
    }, 500);
  }
});
</script>

<style scoped>
.comment-section {
  background: #fff;
  border-radius: 10px;
  padding: 20px;
  max-height: 600px;
  display: flex;
  flex-direction: column;
}

.comment-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 10px;
  border-bottom: 1px solid #eee;
}

.comment-header h3 {
  margin: 0;
  font-size: 18px;
}

.close-btn {
  background: none;
  border: none;
  font-size: 24px;
  cursor: pointer;
  color: #999;
}

.close-btn:hover {
  color: #333;
}

.comment-input-area {
  margin-bottom: 20px;
}

.comment-textarea {
  width: 100%;
  padding: 10px;
  border: 1px solid #ddd;
  border-radius: 5px;
  resize: vertical;
  font-family: inherit;
  margin-bottom: 10px;
}

.submit-btn {
  padding: 8px 20px;
  background: #409eff;
  color: #fff;
  border: none;
  border-radius: 5px;
  cursor: pointer;
}

.submit-btn:hover:not(:disabled) {
  background: #66b1ff;
}

.submit-btn:disabled {
  background: #ccc;
  cursor: not-allowed;
}

.comments-list {
  flex: 1;
  overflow-y: auto;
}

.comment-item {
  padding: 15px 0;
  border-bottom: 1px solid #f0f0f0;
}

.comment-item:last-child {
  border-bottom: none;
}

.comment-header-info {
  display: flex;
  align-items: center;
  margin-bottom: 10px;
}

.comment-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  margin-right: 10px;
}

.comment-user-info {
  display: flex;
  flex-direction: column;
}

.comment-username {
  font-weight: bold;
  font-size: 14px;
}

.comment-time {
  font-size: 12px;
  color: #999;
}

.comment-content {
  margin-bottom: 10px;
  line-height: 1.6;
}

.comment-actions {
  display: flex;
  gap: 15px;
}

.like-btn, .reply-btn {
  background: none;
  border: none;
  cursor: pointer;
  color: #666;
  font-size: 14px;
  padding: 5px 10px;
  border-radius: 5px;
}

.like-btn:hover, .reply-btn:hover {
  background: #f0f0f0;
}

.like-btn.liked {
  color: #409eff;
}

.reply-input-area {
  margin-top: 10px;
  padding: 10px;
  background: #f9f9f9;
  border-radius: 5px;
}

.reply-textarea {
  width: 100%;
  padding: 8px;
  border: 1px solid #ddd;
  border-radius: 5px;
  resize: vertical;
  font-family: inherit;
  margin-bottom: 10px;
}

.reply-actions {
  display: flex;
  gap: 10px;
}

.cancel-btn {
  padding: 8px 20px;
  background: #f0f0f0;
  color: #666;
  border: none;
  border-radius: 5px;
  cursor: pointer;
}

.cancel-btn:hover {
  background: #e0e0e0;
}

.replies-list {
  margin-top: 10px;
  padding-left: 50px;
}

.reply-item {
  display: flex;
  margin-bottom: 10px;
}

.reply-avatar {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  margin-right: 10px;
}

.reply-content-wrapper {
  flex: 1;
}

.reply-user-info {
  display: flex;
  gap: 10px;
  margin-bottom: 5px;
}

.reply-username {
  font-weight: bold;
  font-size: 13px;
}

.reply-time {
  font-size: 12px;
  color: #999;
}

.reply-content {
  font-size: 14px;
  line-height: 1.5;
}

.empty-comments {
  text-align: center;
  padding: 40px;
  color: #999;
}

.highlight-comment {
  background: #fff3cd !important;
  border: 2px solid #ffc107 !important;
  border-radius: 8px;
  animation: highlight-pulse 1s ease-in-out;
}

@keyframes highlight-pulse {
  0%, 100% {
    box-shadow: 0 0 0 0 rgba(255, 193, 7, 0.7);
  }
  50% {
    box-shadow: 0 0 0 10px rgba(255, 193, 7, 0);
  }
}
</style>

