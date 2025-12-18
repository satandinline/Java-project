<template>
  <div class="aigc-container">
    <!-- 顶部论坛入口 -->
    <div class="forum-header">
      <button class="forum-btn" @click="toggleComments">
        <span class="forum-icon">💬</span>
        评论
        <span v-if="unreadNotifications > 0" class="notification-badge">{{ unreadNotifications }}</span>
      </button>
    </div>

    <!-- 评论面板 -->
    <div v-if="showComments" class="comments-panel">
      <CommentSection 
        :resource-id="currentResourceId"
        :user-id="currentUserInfo?.id"
        @close="showComments = false"
      />
    </div>

    <div class="aigc-layout">
      <!-- 左侧：历史会话导航 -->
      <div class="session-nav-panel" :class="{ collapsed: isHistoryCollapsed }">
        <div class="session-nav-header">
          <h3>历史会话</h3>
          <div class="header-actions">
            <button 
              class="toggle-history-btn" 
              @click="toggleHistoryPanel"
              :title="isHistoryCollapsed ? '显示历史记录' : '隐藏历史记录'"
            >
              <span v-if="isHistoryCollapsed">▶</span>
              <span v-else>◀</span>
            </button>
            <button 
              v-if="!isHistoryCollapsed"
              class="new-chat-btn" 
              @click="createNewSession" 
              title="开启新对话"
            >
              <span>+</span>
            </button>
          </div>
        </div>
        <!-- 删除操作栏 -->
        <div class="delete-actions" v-if="!isHistoryCollapsed && sessionHistory.length > 0">
          <button 
            class="delete-btn" 
            @click="deleteSelectedSessions"
            :disabled="selectedSessions.length === 0"
            title="删除选中的会话"
          >
            删除选中 ({{ selectedSessions.length }})
          </button>
          <button 
            class="delete-all-btn" 
            @click="deleteAllSessions"
            title="删除所有会话"
          >
            全部删除
          </button>
        </div>
        <div class="session-list" ref="sessionListRef" v-show="!isHistoryCollapsed">
          <!-- 文字AIGC历史记录 -->
          <div class="history-section">
            <div class="history-section-header" @click="textHistoryExpanded = !textHistoryExpanded">
              <span>📝 文字AIGC历史记录</span>
              <span class="expand-icon">{{ textHistoryExpanded ? '▼' : '▶' }}</span>
            </div>
            <div v-show="textHistoryExpanded" class="history-section-content">
              <div 
                v-for="(session, index) in textSessions" 
                :key="session.id"
                :class="['session-item', { active: currentSessionId === session.id, selected: selectedSessions.includes(session.id) }]"
                @click="handleSessionClick(session.id, $event)"
              >
                <input 
                  type="checkbox" 
                  class="session-checkbox"
                  :checked="selectedSessions.includes(session.id)"
                  @click.stop="toggleSessionSelection(session.id)"
                />
                <div class="session-content" @click="loadSession(session.id)">
                  <div class="session-title">{{ session.title || `会话 ${index + 1}` }}</div>
                  <div class="session-time">{{ formatTime(session.created_at) }}</div>
                  <div class="session-preview">{{ getSessionPreview(session) }}</div>
                </div>
              </div>
              <div v-if="textSessions.length === 0" class="empty-sessions">
                暂无文字AIGC历史记录
              </div>
            </div>
          </div>
          
          <!-- 图片AIGC历史记录 -->
          <div class="history-section">
            <div class="history-section-header" @click="imageHistoryExpanded = !imageHistoryExpanded">
              <span>🎨 图片AIGC历史记录</span>
              <span class="expand-icon">{{ imageHistoryExpanded ? '▼' : '▶' }}</span>
            </div>
            <div v-show="imageHistoryExpanded" class="history-section-content">
              <div 
                v-for="(session, index) in imageSessions" 
                :key="session.id"
                :class="['session-item', { active: currentSessionId === session.id, selected: selectedSessions.includes(session.id) }]"
                @click="handleSessionClick(session.id, $event)"
              >
                <input 
                  type="checkbox" 
                  class="session-checkbox"
                  :checked="selectedSessions.includes(session.id)"
                  @click.stop="toggleSessionSelection(session.id)"
                />
                <div class="session-content" @click="loadSession(session.id)">
                  <div class="session-title">{{ session.title || `会话 ${index + 1}` }}</div>
                  <div class="session-time">{{ formatTime(session.created_at) }}</div>
                  <div class="session-preview">{{ getSessionPreview(session) }}</div>
                </div>
              </div>
              <div v-if="imageSessions.length === 0" class="empty-sessions">
                暂无图片AIGC历史记录
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧：当前对话和输入区域 -->
      <div class="main-panel">
        <!-- 当前对话显示区域 -->
        <div class="conversation-area" ref="conversationAreaRef">
          <div 
            v-for="(msg, index) in currentConversation" 
            :key="index"
            :class="['message-item', msg.role]"
          >
            <div class="message-avatar">
              <img 
                v-if="msg.role === 'user' && currentUserAvatar" 
                :src="getAvatarUrl(currentUserAvatar)" 
                class="avatar-img"
                alt="用户头像"
                @error="handleAvatarError"
              />
              <span v-else-if="msg.role === 'user'">👤</span>
              <span v-else>🤖</span>
            </div>
            <div class="message-content-wrapper">
              <div class="message-role-label">{{ msg.role === 'user' ? (currentUserNickname || '用户') : (msg.model === 'image' ? 'Huoshan' : 'Tongyi') }}</div>
              <!-- AI回答时显示左右分栏 -->
              <div v-if="msg.role === 'assistant' && msg.retrieved_resources" class="ai-response-layout">
                <!-- 左侧：检索到的资源 -->
                <div class="resources-panel">
                  <div class="panel-header">📚 检索资源</div>
                  <div class="resources-content">
                    <!-- 向量库结果 -->
                    <div v-if="msg.retrieved_resources.vector_results && msg.retrieved_resources.vector_results.length > 0" class="resource-section">
                      <div class="resource-section-title">向量库检索</div>
                      <div 
                        v-for="(item, idx) in msg.retrieved_resources.vector_results" 
                        :key="`vec-${idx}`"
                        class="resource-item"
                      >
                        <div class="resource-content">{{ item.content }}</div>
                      </div>
                    </div>
                    <!-- 数据库结果 -->
                    <div v-if="msg.retrieved_resources.database_results && msg.retrieved_resources.database_results.length > 0" class="resource-section">
                      <div class="resource-section-title">数据库检索</div>
                      <div 
                        v-for="(item, idx) in msg.retrieved_resources.database_results" 
                        :key="`db-${idx}`"
                        class="resource-item"
                      >
                        <div class="resource-source">{{ item.table || '数据库' }}</div>
                        <div v-if="item.title" class="resource-title">{{ item.title }}</div>
                        <div v-if="item.content" class="resource-content">{{ item.content }}</div>
                        <div v-if="item.source" class="resource-source-url">{{ item.source }}</div>
                        <div v-if="item.storage_path" class="resource-image">
                          <img :src="getResourceImageUrl(item.storage_path, item.table)" class="resource-img" @click="previewImage(getResourceImageUrl(item.storage_path, item.table))" />
                        </div>
                      </div>
                    </div>
                    <!-- 网页爬取结果 -->
                    <div v-if="msg.retrieved_resources.web_results && msg.retrieved_resources.web_results.length > 0" class="resource-section">
                      <div class="resource-section-title">网页检索</div>
                      <div 
                        v-for="(item, idx) in msg.retrieved_resources.web_results" 
                        :key="`web-${idx}`"
                        class="resource-item"
                      >
                        <div v-if="item.title" class="resource-title">{{ item.title }}</div>
                        <div class="resource-content">{{ item.content }}</div>
                        <div v-if="item.source" class="resource-source-url">
                          <a :href="item.source" target="_blank">{{ item.source }}</a>
                        </div>
                      </div>
                    </div>
                    <div v-if="!msg.retrieved_resources.vector_results?.length && !msg.retrieved_resources.database_results?.length && !msg.retrieved_resources.web_results?.length" class="no-resources">
                      未检索到相关资源
                    </div>
                  </div>
                </div>
                <!-- 右侧：AI生成的答案 -->
                <div class="answer-panel">
                  <div class="panel-header">💡 AI回答</div>
                  <div class="answer-content">
                    <div class="message-text" v-html="formatAnswerText(msg.content)"></div>
                    <div v-if="msg.image_path" class="message-image-result">
                      <img :src="getImageUrl(msg.image_path)" class="result-image" @click="previewImage(getImageUrl(msg.image_path))" />
                    </div>
                    <div v-if="msg.key_entities && msg.key_entities.length > 0" class="key-entities">
                      <div class="entities-label">关键实体：</div>
                      <div class="entities-list">
                        <span v-for="(entity, idx) in msg.key_entities" :key="idx" class="entity-tag">{{ entity }}</span>
                      </div>
                    </div>
                    <div v-if="msg.sources" class="sources-info">
                      <div class="sources-label">参考来源：</div>
                      <div class="sources-text">{{ msg.sources }}</div>
                    </div>
                  </div>
                </div>
              </div>
              <!-- 用户消息或没有资源的AI消息 -->
              <div v-else class="message-content">
                <div v-if="msg.images && msg.images.length > 0" class="message-images">
                  <img 
                    v-for="(img, imgIdx) in msg.images" 
                    :key="imgIdx"
                    :src="img"
                    class="message-image"
                    @click="previewImage(img)"
                  />
                </div>
                <div v-if="msg.role === 'user' && msg.content" class="message-text" v-html="formatAnswerText(msg.content)"></div>
                <div v-else-if="msg.role === 'assistant'" class="message-text" v-html="formatAnswerText(msg.content)"></div>
                <div v-if="msg.image_path" class="message-image-result">
                  <img :src="getImageUrl(msg.image_path)" class="result-image" @click="previewImage(getImageUrl(msg.image_path))" />
                </div>
              </div>
              <div class="message-time">{{ formatTime(msg.timestamp) }}</div>
            </div>
          </div>
          <div v-if="currentConversation.length === 0" class="empty-conversation">
            <div class="empty-icon">💬</div>
            <div class="empty-text">开始新的对话吧</div>
          </div>
        </div>

        <!-- 输入区域（页面中部） -->
        <div class="input-area">
          <!-- 模式切换和图片上传 -->
          <div class="input-toolbar">
            <div class="mode-switch">
              <button 
                :class="['mode-btn', { active: aigcMode === 'text' }]"
                @click="aigcMode = 'text'"
              >
                📝 文字AIGC
              </button>
              <button 
                :class="['mode-btn', { active: aigcMode === 'image' }]"
                @click="aigcMode = 'image'"
              >
                🎨 图片AIGC
              </button>
            </div>
            <label class="upload-btn">
              <input 
                type="file" 
                accept="image/*" 
                multiple 
                @change="handleImageUpload"
                style="display: none;"
              />
              <span class="upload-icon">📷</span>
              上传图片
            </label>
          </div>

          <!-- 已上传的图片预览 -->
          <div v-if="uploadedImages.length > 0" class="uploaded-images">
            <div 
              v-for="(img, index) in uploadedImages" 
              :key="index"
              class="uploaded-image-item"
            >
              <img :src="img" class="preview-img" />
              <button class="remove-btn" @click="removeImage(index)">×</button>
            </div>
          </div>

          <!-- 文本输入和发送 -->
          <div class="text-input-section">
            <textarea
              v-model="userInput"
              :placeholder="aigcMode === 'text' ? '请输入您的问题或需求...' : '请输入图片生成提示词...'"
              class="text-input"
              @keydown.enter.exact.prevent="sendMessage"
              @keydown.enter.shift.exact="userInput += '\n'"
            ></textarea>
            <button 
              class="send-btn" 
              @click="sendMessage"
              :disabled="isLoading || (!userInput.trim() && uploadedImages.length === 0)"
            >
              <span v-if="isLoading">生成中...</span>
              <span v-else>发送</span>
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 图片预览模态框 -->
    <div v-if="previewImageUrl" class="image-preview-modal" @click="previewImageUrl = null">
      <img :src="previewImageUrl" class="preview-modal-image" @click.stop />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted } from 'vue';
import CommentSection from './CommentSection.vue';

// 获取当前登录用户信息
const getCurrentUser = () => {
  const userInfoStr = localStorage.getItem('userInfo');
  if (userInfoStr) {
    try {
      return JSON.parse(userInfoStr);
    } catch (e) {
      console.error('解析用户信息失败:', e);
      return null;
    }
  }
  return null;
};

// 获取用户昵称和头像
const currentUserInfo = computed(() => getCurrentUser());
const currentUserNickname = computed(() => currentUserInfo.value?.nickname || currentUserInfo.value?.username || '用户');
const currentUserAvatar = computed(() => currentUserInfo.value?.avatar_path || './default.jpg');

// 获取头像URL
const getAvatarUrl = (avatarPath) => {
  if (!avatarPath) return '/default.jpg';
  if (avatarPath.startsWith('http://') || avatarPath.startsWith('https://')) {
    return avatarPath;
  }
  if (avatarPath.startsWith('/')) {
    return avatarPath;
  }
  if (avatarPath.startsWith('./')) {
    return avatarPath.replace('./', '/');
  }
  return '/' + avatarPath;
};

// 处理头像加载错误
const handleAvatarError = (event) => {
  event.target.src = '/default.jpg';
};

// 会话管理
const sessionHistory = ref([]);
const currentSessionId = ref(null);
const currentConversation = ref([]);
const selectedSessions = ref([]); // 选中的会话ID列表
const isHistoryCollapsed = ref(false); // 历史记录面板是否折叠
const textHistoryExpanded = ref(true); // 文字AIGC历史记录是否展开
const imageHistoryExpanded = ref(true); // 图片AIGC历史记录是否展开

// 计算属性：按模式分类会话
const textSessions = computed(() => {
  // 确保mode字段正确：如果mode是'image'，不应该出现在textSessions中
  return sessionHistory.value.filter(s => {
    const mode = s.mode || 'text';
    return mode === 'text';
  });
});

const imageSessions = computed(() => {
  // 确保mode字段正确：如果mode是'text'，不应该出现在imageSessions中
  return sessionHistory.value.filter(s => {
    const mode = s.mode || 'text';
    return mode === 'image';
  });
});

// 输入相关
const userInput = ref('');
const uploadedImages = ref([]);
const aigcMode = ref('text'); // 'text' 或 'image'
const isLoading = ref(false);

// UI引用
const sessionListRef = ref(null);
const conversationAreaRef = ref(null);
const previewImageUrl = ref(null);
const showComments = ref(false);
const currentResourceId = ref(1); // 默认资源ID，可以根据实际情况修改
const unreadNotifications = ref(0);

// 格式化时间
const formatTime = (timestamp) => {
  if (!timestamp) return '';
  const date = new Date(timestamp);
  return date.toLocaleString('zh-CN', { 
    month: '2-digit', 
    day: '2-digit', 
    hour: '2-digit', 
    minute: '2-digit' 
  });
};

// 提取对话主题（不超过20字）- 调用阿里云API
const extractConversationTitle = async (messages) => {
  if (!messages || messages.length === 0) {
    return '新对话';
  }
  
  // 整合用户输入和AI回答
  let conversationText = '';
  messages.forEach(msg => {
    if (msg.role === 'user') {
      conversationText += `用户：${msg.content}\n`;
    } else if (msg.role === 'assistant') {
      conversationText += `AI：${msg.content}\n`;
    }
  });
  
  // 如果对话文本太长，截取前500字（保留更多上下文）
  if (conversationText.length > 500) {
    conversationText = conversationText.substring(0, 500) + '...';
  }
  
  // 调用后端API提取主题（后端会调用阿里云API）
  try {
    const response = await fetch('/api/aigc/extract-title', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ conversation: conversationText })
    });
    
    if (response.ok) {
      const result = await response.json();
      if (result.title && result.title.trim() && result.title !== '新对话') {
        // 确保标题不超过20字
        let title = result.title.trim();
        if (title.length > 20) {
          title = title.substring(0, 20);
        }
        return title;
      }
    } else {
      console.warn('提取主题API调用失败，使用降级方案');
    }
  } catch (error) {
    console.error('提取主题失败:', error);
  }
  
  // 降级方案：从对话中提取关键词
  // 优先使用第一条用户消息和第一条AI回答的组合
  const firstUserMsg = messages.find(m => m.role === 'user');
  const firstAIMsg = messages.find(m => m.role === 'assistant');
  
  if (firstUserMsg && firstUserMsg.content) {
    let title = firstUserMsg.content.trim();
    // 移除标点符号和多余空格
    title = title.replace(/[，。！？、；：\s]+/g, ' ').trim();
    
    // 如果AI回答存在且用户消息较短，可以结合AI回答的关键词
    if (firstAIMsg && firstAIMsg.content && title.length < 15) {
      const aiContent = firstAIMsg.content.trim();
      // 提取AI回答中的关键词（前10个字）
      const aiKeywords = aiContent.substring(0, 10).replace(/[，。！？、；：\s]+/g, '');
      if (aiKeywords) {
        title = title + ' ' + aiKeywords;
      }
    }
    
    // 如果超过20字，截取前20字
    if (title.length > 20) {
      title = title.substring(0, 20);
    }
    return title || '新对话';
  }
  
  return '新对话';
};

// 获取会话预览文本
const getSessionPreview = (session) => {
  // 如果会话有消息数量信息，显示消息数量
  if (session.message_count !== undefined) {
    return session.message_count > 0 ? `${session.message_count} 条消息` : '空会话';
  }
  // 否则尝试从当前加载的消息中获取
  if (session.messages && session.messages.length > 0) {
    const firstMsg = session.messages[0];
    return firstMsg.content.substring(0, 30) + (firstMsg.content.length > 30 ? '...' : '');
  }
  return '空会话';
};

// 创建新会话
const createNewSession = async () => {
  // 保存当前会话
  if (currentSessionId.value && currentConversation.value.length > 0) {
    await saveCurrentSession();
  }
  
  const currentUser = getCurrentUser();
  if (!currentUser || !currentUser.id) {
    alert('请先登录');
    return null;
  }
  
  try {
    const response = await fetch('/api/aigc/sessions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-User-Id': currentUser.id.toString()
      },
      body: JSON.stringify({
        summary: '新对话',
        mode: aigcMode.value  // 传递当前模式
      })
    });
    
    const data = await response.json();
    if (data.success && data.session) {
      const newSession = {
        id: data.session.id,
        title: data.session.summary || '新对话',
        created_at: data.session.created_at,
        mode: data.session.mode || aigcMode.value,  // 保存模式
        messages: []
      };
      sessionHistory.value.unshift(newSession);
      currentSessionId.value = newSession.id;
      currentConversation.value = [];
      userInput.value = '';
      uploadedImages.value = [];
      return newSession;
    } else {
      console.error('创建会话失败:', data.message);
      return null;
    }
  } catch (error) {
    console.error('创建会话失败:', error);
    return null;
  }
};

// 加载会话
const loadSession = async (sessionId) => {
  const currentUser = getCurrentUser();
  if (!currentUser || !currentUser.id) {
    alert('请先登录');
    return;
  }
  
  // 检查会话模式是否与当前模式匹配
  const session = sessionHistory.value.find(s => s.id === sessionId);
  if (session && session.mode && session.mode !== aigcMode.value) {
    // 如果模式不匹配，切换模式
    aigcMode.value = session.mode;
  }
  
  try {
    const response = await fetch(`/api/aigc/sessions/${sessionId}/messages?user_id=${currentUser.id}`, {
      method: 'GET',
      headers: {
        'X-User-Id': currentUser.id.toString()
      }
    });
    
    const data = await response.json();
    if (data.success && data.messages) {
      currentSessionId.value = sessionId;
      // 转换消息格式以匹配前端显示（使用新表结构）
      currentConversation.value = data.messages.map(msg => {
        const message = {
          role: msg.role === 'user' ? 'user' : 'assistant',
          content: msg.content || '',
          timestamp: msg.timestamp,
          retrieved_resources: msg.retrieved_resources || null,
          key_entities: msg.key_entities || [],
          sources: msg.sources || '',
          image_path: msg.image_path || null,
          images: msg.images || [],
          model: msg.model || (session.mode || 'text')  // 添加模型类型
        };
        // 确保用户消息有内容显示
        if (message.role === 'user' && !message.content) {
          message.content = '[用户消息]';
        }
        return message;
      });
      // 滚动到底部
      await nextTick();
      scrollToBottom();
    } else {
      console.error('加载会话失败:', data.message);
    }
  } catch (error) {
    console.error('加载会话失败:', error);
  }
};

// 保存当前会话（每次保存时自动提取主题，调用阿里云API生成）
const saveCurrentSession = async () => {
  if (!currentSessionId.value || currentConversation.value.length === 0) {
    return;
  }
  
  const currentUser = getCurrentUser();
  if (!currentUser || !currentUser.id) {
    return;
  }
  
  // 提取/更新对话主题
  let title = '新对话';
  if (currentConversation.value.length > 0) {
    try {
      // 调用后端API提取主题（后端会调用阿里云API生成）
      title = await extractConversationTitle(currentConversation.value);
      if (!title || !title.trim() || title === '新对话') {
        // 如果提取失败，使用降级方案
        const firstUserMsg = currentConversation.value.find(m => m.role === 'user');
        if (firstUserMsg && firstUserMsg.content) {
          let fallbackTitle = firstUserMsg.content.trim();
          fallbackTitle = fallbackTitle.replace(/[，。！？、；：\s]+/g, ' ').trim();
          if (fallbackTitle.length > 20) {
            fallbackTitle = fallbackTitle.substring(0, 20);
          }
          title = fallbackTitle || '新对话';
        }
      }
    } catch (error) {
      console.error('[前端] 提取主题失败:', error);
      // 提取失败时使用降级方案
      const firstUserMsg = currentConversation.value.find(m => m.role === 'user');
      if (firstUserMsg && firstUserMsg.content) {
        let fallbackTitle = firstUserMsg.content.trim();
        fallbackTitle = fallbackTitle.replace(/[，。！？、；：\s]+/g, ' ').trim();
        if (fallbackTitle.length > 20) {
          fallbackTitle = fallbackTitle.substring(0, 20);
        }
        title = fallbackTitle || '新对话';
      }
    }
  }
  
  // 更新会话摘要到数据库
  try {
    await fetch(`/api/aigc/sessions/${currentSessionId.value}/summary`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'X-User-Id': currentUser.id.toString()
      },
      body: JSON.stringify({
        summary: title
      })
    });
    
    // 更新本地会话列表中的标题
    const session = sessionHistory.value.find(s => s.id === currentSessionId.value);
    if (session) {
      session.title = title;
    }
  } catch (error) {
    console.error('更新会话摘要失败:', error);
  }
};

// 处理图片上传
const handleImageUpload = (event) => {
  const files = event.target.files;
  if (files && files.length > 0) {
    Array.from(files).forEach(file => {
      if (file.type.startsWith('image/')) {
        const reader = new FileReader();
        reader.onload = (e) => {
          uploadedImages.value.push(e.target.result);
        };
        reader.readAsDataURL(file);
      }
    });
  }
};

// 移除图片
const removeImage = (index) => {
  uploadedImages.value.splice(index, 1);
};

// 预览图片
const previewImage = (url) => {
  previewImageUrl.value = url;
};

// 发送消息（支持流式输出）
const sendMessage = async () => {
  if (isLoading.value) return;
  
  // 验证输入：文本模式和图片模式都需要有内容
  const inputText = userInput.value.trim();
  if (aigcMode.value === 'text' && !inputText) {
    alert('请输入您的问题');
    return;
  }
  if (aigcMode.value === 'image' && !inputText && uploadedImages.value.length === 0) {
    alert('请输入图片生成提示词或上传参考图片');
    return;
  }

  // 检查当前会话的模式是否与当前模式匹配
  if (currentSessionId.value) {
    const currentSession = sessionHistory.value.find(s => s.id === currentSessionId.value);
    if (currentSession && currentSession.mode && currentSession.mode !== aigcMode.value) {
      // 如果模式不匹配，提示用户并创建新会话
      if (!confirm(`当前会话是${currentSession.mode === 'text' ? '文字' : '图片'}AIGC模式，您正在使用${aigcMode.value === 'text' ? '文字' : '图片'}AIGC模式。是否创建新会话？`)) {
        return;
      }
      // 保存当前会话
      await saveCurrentSession();
      // 创建新会话
      const newSession = await createNewSession();
      if (!newSession) {
        alert('创建会话失败，请稍后重试');
        return;
      }
    }
  } else {
    // 如果没有当前会话，创建新会话
    const newSession = await createNewSession();
    if (!newSession) {
      alert('创建会话失败，请稍后重试');
      return;
    }
  }

  const userMessage = {
    role: 'user',
    content: userInput.value.trim(),
    images: aigcMode.value === 'image' ? [...uploadedImages.value] : [],
    mode: aigcMode.value,
    timestamp: new Date().toISOString()
  };

  currentConversation.value.push(userMessage);
  
  // 注意：用户消息和AI消息将一起保存，所以这里先不保存
  
  // inputText已在上面声明，这里直接使用
  userInput.value = '';
  uploadedImages.value = [];
  isLoading.value = true;

  // 创建AI消息占位符（用于流式更新）
  const aiMessage = {
    role: 'assistant',
    content: '',
    retrieved_resources: null,
    key_entities: [],
    sources: '',
    image_path: null,
    model: aigcMode.value,  // 设置模型类型，用于显示AI昵称
    timestamp: new Date().toISOString()
  };
  currentConversation.value.push(aiMessage);

  // 滚动到底部
  await nextTick();
  scrollToBottom();

  try {
    // 获取当前用户信息
    const currentUser = getCurrentUser();
    if (!currentUser || !currentUser.id) {
      throw new Error('用户未登录，请先登录');
    }

    // 调用后端API（普通模式，不使用流式输出）
    const formData = new FormData();
    formData.append('query', inputText);
    formData.append('mode', aigcMode.value);
    formData.append('stream', 'false');  // 禁用流式输出
    
    // 添加session_id（如果存在）
    if (currentSessionId.value) {
      formData.append('session_id', currentSessionId.value.toString());
    }
    
    if (aigcMode.value === 'image' && userMessage.images.length > 0) {
      userMessage.images.forEach((img, idx) => {
        const blob = dataURLtoBlob(img);
        formData.append(`images`, blob, `image_${idx}.jpg`);
      });
    }

    // 使用EventSource或fetch处理流式响应
    const response = await fetch('/api/aigc/chat', {
      method: 'POST',
      headers: {
        'X-User-Id': currentUser.id.toString()  // 在请求头中添加用户ID
      },
      body: formData
    });

    if (!response.ok) {
      // 尝试读取错误响应
      let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
      try {
        // 对于流式响应，需要先读取响应体
        const contentType = response.headers.get('content-type');
        if (contentType && contentType.includes('application/json')) {
          const errorData = await response.json();
          if (errorData.error || errorData.answer) {
            errorMessage = errorData.answer || errorData.error || errorMessage;
          }
        } else {
          // 对于非JSON响应，尝试读取文本
          const text = await response.text();
          if (text) {
            try {
              const errorData = JSON.parse(text);
              errorMessage = errorData.answer || errorData.error || errorMessage;
            } catch {
              errorMessage = text.substring(0, 200) || errorMessage;
            }
          }
        }
      } catch (e) {
        console.error('解析错误响应失败:', e);
        // 使用默认错误信息
      }
      throw new Error(errorMessage);
    }

    // 处理JSON响应（非流式）
    try {
      const data = await response.json();
      
      if (data.error) {
        aiMessage.content = data.answer || data.error || '处理失败';
      } else {
        aiMessage.content = data.answer || '处理成功';
        
        // 处理图片路径（图片AIGC模式）
        if (data.image_path) {
          aiMessage.image_path = data.image_path;
        }
        
        // 设置模型类型（用于显示AI昵称）
        // 优先使用后端返回的model，如果没有则使用当前模式
        aiMessage.model = data.model || aigcMode.value;  // 'text' 或 'image'
        
        // 处理其他字段
        if (data.key_entities) {
          aiMessage.key_entities = data.key_entities;
        }
        if (data.sources) {
          aiMessage.sources = data.sources;
        }
        if (data.retrieved_resources) {
          aiMessage.retrieved_resources = data.retrieved_resources;
        }
      }
      
      // 注意：消息已在后端AIGC chat接口中自动保存，这里不需要再次保存
    } catch (e) {
      console.error('解析JSON响应失败:', e);
      aiMessage.content = '解析响应失败，请稍后重试';
    }

    // 确保内容不为空
    if (!aiMessage.content) {
      aiMessage.content = '抱歉，未能生成有效回答。';
    }

    await saveCurrentSession();
  } catch (error) {
    console.error('发送消息失败:', error);
    const errorMessage = error.message || '未知错误';
    let errorContent = `抱歉，生成失败：${errorMessage}。`;
    
    // 提供更友好的错误提示
    if (errorMessage.includes('Failed to fetch') || errorMessage.includes('NetworkError')) {
      errorContent += '\n\n请确保：\n1. 后端API服务器已启动（运行 python aigc_api_server.py）\n2. 后端服务正常运行（查看终端输出）\n3. 检查网络连接';
    } else if (errorMessage.includes('未初始化') || errorMessage.includes('未配置')) {
      errorContent += '\n\n请检查：\n1. API密钥是否正确配置在.env文件中\n2. 数据库连接是否正常';
    }
    
    aiMessage.content = errorContent;
    await saveCurrentSession();
  } finally {
    isLoading.value = false;
    await nextTick();
    scrollToBottom();
  }
};

// Base64转Blob
const dataURLtoBlob = (dataURL) => {
  const arr = dataURL.split(',');
  const mime = arr[0].match(/:(.*?);/)[1];
  const bstr = atob(arr[1]);
  let n = bstr.length;
  const u8arr = new Uint8Array(n);
  while (n--) {
    u8arr[n] = bstr.charCodeAt(n);
  }
  return new Blob([u8arr], { type: mime });
};

// 滚动到底部
const scrollToBottom = () => {
  if (conversationAreaRef.value) {
    conversationAreaRef.value.scrollTop = conversationAreaRef.value.scrollHeight;
  }
};

// 切换评论面板
const toggleComments = () => {
  showComments.value = !showComments.value;
  if (showComments.value) {
    loadNotifications();
  }
};

// 加载未读通知
const loadNotifications = async () => {
  try {
    const userInfo = getCurrentUser();
    if (!userInfo || !userInfo.id) return;
    
    const response = await fetch(`/api/notifications?user_id=${userInfo.id}&is_read=0`);
    const data = await response.json();
    
    if (data.success) {
      unreadNotifications.value = data.notifications?.length || 0;
    }
  } catch (error) {
    console.error('加载通知失败:', error);
  }
};

// 格式化答案文本（支持换行等）
const formatAnswerText = (text) => {
  if (!text) return '';
  // 将换行符转换为HTML换行
  return text.replace(/\n/g, '<br>');
};

// 获取资源图片URL
const getResourceImageUrl = (storagePath, tableName) => {
  if (!storagePath) return '';
  
  // 根据表名确定文件夹
  let folder = '';
  if (tableName === 'AIGC_graph') {
    folder = '/AIGC_graph/';
  } else if (tableName === 'crawled_images') {
    folder = '/crawled_images/';
  } else {
    folder = '/images/';
  }
  
  // 如果storagePath已经是完整路径，直接返回
  if (storagePath.startsWith('http://') || storagePath.startsWith('https://')) {
    return storagePath;
  }
  
  // 否则拼接路径
  return folder + storagePath.replace(/^\/+/, '');
};

// 获取图片URL（用于AIGC生成的图片和用户上传的图片）
// 参考头像显示方法：如果以 / 开头，直接返回（已经是正确的路径格式）
const getImageUrl = (imagePath) => {
  if (!imagePath) return '';
  
  // 如果已经是完整URL，直接返回
  if (imagePath.startsWith('http://') || imagePath.startsWith('https://')) {
    return imagePath;
  }
  
  // 处理绝对路径（Windows路径，如：D:\git\mygit\Java-project\AIGC_graph\0001.jpeg）
  // 或包含绝对路径的相对路径（如：/AIGC_graph/D:\git\mygit\Java-project\AIGC_graph\0001.jpeg）
  if (imagePath.includes(':\\') || imagePath.includes(':/')) {
    // 提取文件名
    const parts = imagePath.split(/[/\\]/);
    const filename = parts[parts.length - 1];
    // 如果文件名存在，根据路径判断是AIGC_graph还是image_from_users
    if (filename) {
      if (imagePath.includes('AIGC_graph')) {
        return `/AIGC_graph/${filename}`;
      } else if (imagePath.includes('image_from_users')) {
        return `/image_from_users/${filename}`;
      } else {
        return `/AIGC_graph/${filename}`;  // 默认
      }
    }
  }
  
  // 如果以 / 开头，直接返回（已经是正确的路径格式，参考头像显示方法）
  if (imagePath.startsWith('/')) {
    // 如果路径中包含Windows绝对路径特征，提取文件名
    if (imagePath.includes(':\\') || imagePath.includes(':/')) {
      const parts = imagePath.split(/[/\\]/);
      const filename = parts[parts.length - 1];
      if (filename) {
        // 根据路径判断文件夹
        if (imagePath.includes('AIGC_graph')) {
          return `/AIGC_graph/${filename}`;
        } else if (imagePath.includes('image_from_users')) {
          return `/image_from_users/${filename}`;
        } else {
          return `/AIGC_graph/${filename}`;  // 默认
        }
      }
    }
    // 否则直接返回（已经是正确的相对路径格式，如：/AIGC_graph/0001.jpeg 或 /image_from_users/xxx.jpg）
    return imagePath;
  }
  
  // 如果以 ./ 开头，转换为 / 开头
  if (imagePath.startsWith('./')) {
    return imagePath.replace('./', '/');
  }
  
  // 其他情况，添加 / 前缀
  return '/' + imagePath;
};

// 从数据库加载会话列表
const loadSessionsFromDB = async () => {
  const currentUser = getCurrentUser();
  if (!currentUser || !currentUser.id) {
    return;
  }
  
  try {
    const response = await fetch(`/api/aigc/sessions?user_id=${currentUser.id}`, {
      method: 'GET',
      headers: {
        'X-User-Id': currentUser.id.toString()
      }
    });
    
    const data = await response.json();
    if (data.success && data.sessions) {
      sessionHistory.value = data.sessions.map(session => ({
        id: session.id,
        title: session.summary || '新对话',
        created_at: session.created_at,
        mode: session.mode || 'text',  // 保存模式，确保从数据库正确读取
        message_count: session.message_count || 0
      }));
      // 调试：打印会话模式
      console.log('加载的会话列表:', sessionHistory.value.map(s => ({ id: s.id, mode: s.mode })));
    } else {
      console.error('加载会话列表失败:', data.message);
      sessionHistory.value = [];
    }
  } catch (error) {
    console.error('加载会话列表失败:', error);
    sessionHistory.value = [];
  }
};

// 切换历史记录面板显示/隐藏
const toggleHistoryPanel = () => {
  isHistoryCollapsed.value = !isHistoryCollapsed.value;
  // 保存状态到本地存储
  localStorage.setItem('aigc_history_collapsed', isHistoryCollapsed.value.toString());
};

// 处理会话点击（区分复选框和内容区域）
const handleSessionClick = (sessionId, event) => {
  // 如果点击的是复选框区域，不加载会话
  if (event.target.classList.contains('session-checkbox') || event.target.closest('.session-checkbox')) {
    return;
  }
  loadSession(sessionId);
};

// 切换会话选择状态
const toggleSessionSelection = (sessionId) => {
  const index = selectedSessions.value.indexOf(sessionId);
  if (index > -1) {
    selectedSessions.value.splice(index, 1);
  } else {
    selectedSessions.value.push(sessionId);
  }
};

// 删除选中的会话
const deleteSelectedSessions = async () => {
  if (selectedSessions.value.length === 0) {
    return;
  }
  
  if (!confirm(`确定要删除选中的 ${selectedSessions.value.length} 个会话吗？此操作不可恢复。`)) {
    return;
  }
  
  const currentUser = getCurrentUser();
  if (!currentUser || !currentUser.id) {
    alert('请先登录');
    return;
  }
  
  try {
    const response = await fetch('/api/aigc/sessions/batch', {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
        'X-User-Id': currentUser.id.toString()
      },
      body: JSON.stringify({
        session_ids: selectedSessions.value
      })
    });
    
    const data = await response.json();
    if (data.success) {
      // 如果当前会话被删除，清空对话
      if (selectedSessions.value.includes(currentSessionId.value)) {
        currentSessionId.value = null;
        currentConversation.value = [];
      }
      
      // 从列表中移除已删除的会话
      sessionHistory.value = sessionHistory.value.filter(
        s => !selectedSessions.value.includes(s.id)
      );
      
      // 清空选中列表
      selectedSessions.value = [];
      
      alert('删除成功');
    } else {
      alert('删除失败：' + (data.message || '未知错误'));
    }
  } catch (error) {
    console.error('删除会话失败:', error);
    alert('删除失败，请稍后重试');
  }
};

// 删除所有会话
const deleteAllSessions = async () => {
  if (sessionHistory.value.length === 0) {
    return;
  }
  
  if (!confirm(`确定要删除所有 ${sessionHistory.value.length} 个会话吗？此操作不可恢复。`)) {
    return;
  }
  
  const currentUser = getCurrentUser();
  if (!currentUser || !currentUser.id) {
    alert('请先登录');
    return;
  }
  
  try {
    const response = await fetch('/api/aigc/sessions/all', {
      method: 'DELETE',
      headers: {
        'X-User-Id': currentUser.id.toString()
      }
    });
    
    const data = await response.json();
    if (data.success) {
      // 清空当前会话和对话
      currentSessionId.value = null;
      currentConversation.value = [];
      sessionHistory.value = [];
      selectedSessions.value = [];
      
      alert('删除成功');
    } else {
      alert('删除失败：' + (data.message || '未知错误'));
    }
  } catch (error) {
    console.error('删除所有会话失败:', error);
    alert('删除失败，请稍后重试');
  }
};

onMounted(async () => {
  // 从本地存储恢复历史记录面板状态
  const savedCollapsedState = localStorage.getItem('aigc_history_collapsed');
  if (savedCollapsedState !== null) {
    isHistoryCollapsed.value = savedCollapsedState === 'true';
  }
  
  // 加载未读通知
  loadNotifications();
  
  // 从数据库加载历史会话
  await loadSessionsFromDB();
  
  // 从URL参数中恢复对话（如果有）
  const urlParams = new URLSearchParams(window.location.search);
  const conversationParam = urlParams.get('conversation');
  if (conversationParam) {
    try {
      const messages = JSON.parse(decodeURIComponent(conversationParam));
      const newSession = await createNewSession();
      if (newSession) {
        // 将消息保存到数据库
        for (const msg of messages) {
          await fetch(`/api/aigc/sessions/${newSession.id}/messages`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'X-User-Id': getCurrentUser().id.toString()
            },
            body: JSON.stringify({
              sender: msg.role === 'user' ? 'user' : 'ai',
              content: msg.content || ''
            })
          });
        }
        currentConversation.value = messages;
      }
    } catch (e) {
      console.error('恢复对话失败:', e);
    }
  }
});
</script>

<style scoped>
.aigc-container {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 60px);
  background: #f5f7fa;
}

.forum-header {
  display: flex;
  justify-content: flex-end;
  padding: 12px 30px;
  background: white;
  border-bottom: 1px solid #eee;
}

.forum-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  background: #409eff;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  transition: background 0.3s;
}

.forum-btn:hover {
  background: #66b1ff;
}

.forum-icon {
  font-size: 16px;
}

.aigc-layout {
  display: flex;
  flex: 1;
  overflow: hidden;
}

/* 左侧历史会话导航 */
.session-nav-panel {
  width: 220px;
  background: white;
  border-right: 1px solid #eee;
  display: flex;
  flex-direction: column;
  transition: width 0.3s ease;
}

.session-nav-panel.collapsed {
  width: 50px;
}

.session-nav-panel.collapsed .session-nav-header h3,
.session-nav-panel.collapsed .delete-actions,
.session-nav-panel.collapsed .session-list {
  display: none;
}

.session-nav-panel.collapsed .header-actions {
  justify-content: center;
  width: 100%;
}

.session-nav-header {
  padding: 15px;
  border-bottom: 1px solid #eee;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.toggle-history-btn {
  width: 28px;
  height: 28px;
  background: #f0f2f5;
  color: #666;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  cursor: pointer;
  font-size: 12px;
  line-height: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.3s;
  padding: 0;
}

.toggle-history-btn:hover {
  background: #e4e7ed;
  color: #409eff;
}

.session-nav-header h3 {
  margin: 0;
  font-size: 16px;
  color: #333;
  font-weight: 500;
}

.new-chat-btn {
  width: 28px;
  height: 28px;
  background: #409eff;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 20px;
  line-height: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.3s;
  padding: 0;
}

.new-chat-btn:hover {
  background: #66b1ff;
}

.new-chat-btn span {
  font-weight: 300;
}

.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 10px;
}

.session-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 12px;
  margin-bottom: 8px;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
  background: #f9f9f9;
  border: 1px solid transparent;
}

.session-item:hover {
  background: #f0f0f0;
}

.session-item.active {
  background: #e3f2fd;
  border-color: #409eff;
}

.session-title {
  font-size: 14px;
  font-weight: 500;
  color: #333;
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-time {
  font-size: 11px;
  color: #999;
  margin-bottom: 4px;
}

.session-preview {
  font-size: 12px;
  color: #666;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.empty-sessions {
  text-align: center;
  color: #999;
  padding: 20px;
  font-size: 13px;
}

.history-section {
  margin-bottom: 16px;
}

.history-section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  background: #f5f7fa;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  color: #333;
  transition: background 0.3s;
}

.history-section-header:hover {
  background: #e4e7ed;
}

.expand-icon {
  font-size: 12px;
  color: #666;
}

.history-section-content {
  margin-top: 8px;
}

/* 删除操作栏 */
.delete-actions {
  padding: 10px;
  border-bottom: 1px solid #eee;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.delete-btn,
.delete-all-btn {
  flex: 1;
  padding: 6px 12px;
  background: #f56c6c;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  transition: background 0.3s;
  min-width: 80px;
}

.delete-btn:hover:not(:disabled) {
  background: #f78989;
}

.delete-btn:disabled {
  background: #ccc;
  cursor: not-allowed;
}

.delete-all-btn {
  background: #e6a23c;
}

.delete-all-btn:hover {
  background: #ebb563;
}

.session-item.selected {
  background: #fff3e0;
  border-color: #ff9800;
}

.session-checkbox {
  margin-top: 2px;
  cursor: pointer;
  flex-shrink: 0;
}

.session-content {
  flex: 1;
  min-width: 0;
}

/* 右侧主面板 */
.main-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: white;
  overflow: hidden;
}

/* 对话显示区域 */
.conversation-area {
  flex: 1;
  overflow-y: auto;
  padding: 20px 30px;
  background: #fafafa;
}

.message-item {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
}

.message-item.user {
  flex-direction: row;
}

.message-item.assistant {
  flex-direction: row;
}

.message-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: #e4e7ed;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  flex-shrink: 0;
  overflow: hidden;
}

.avatar-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.message-item.user .message-avatar {
  background: #409eff;
}

.message-item.assistant .message-avatar {
  background: #67c23a;
}

.message-content-wrapper {
  flex: 1;
  max-width: calc(100% - 48px);
}

.message-role-label {
  font-size: 12px;
  color: #999;
  margin-bottom: 4px;
}

.message-content {
  background: white;
  padding: 12px 16px;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}

.message-item.user .message-content {
  background: #e3f2fd;
}

.message-text {
  font-size: 14px;
  color: #333;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

/* AI回答左右分栏布局 */
.ai-response-layout {
  display: flex;
  gap: 16px;
  width: 100%;
  min-height: 300px;
}

.resources-panel,
.answer-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: white;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  overflow: hidden;
}

.panel-header {
  padding: 12px 16px;
  background: #f5f7fa;
  border-bottom: 1px solid #e4e7ed;
  font-size: 14px;
  font-weight: 500;
  color: #333;
}

.resources-content,
.answer-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  max-height: 600px;
}

.resource-section {
  margin-bottom: 20px;
}

.resource-section:last-child {
  margin-bottom: 0;
}

.resource-section-title {
  font-size: 13px;
  font-weight: 600;
  color: #409eff;
  margin-bottom: 12px;
  padding-bottom: 6px;
  border-bottom: 1px solid #e4e7ed;
}

.resource-item {
  padding: 12px;
  margin-bottom: 12px;
  background: #f9f9f9;
  border-radius: 6px;
  border-left: 3px solid #409eff;
}

.resource-item:last-child {
  margin-bottom: 0;
}

.resource-source {
  font-size: 12px;
  color: #909399;
  margin-bottom: 6px;
}

.resource-title {
  font-size: 14px;
  font-weight: 500;
  color: #333;
  margin-bottom: 8px;
}

.resource-content {
  font-size: 13px;
  color: #606266;
  line-height: 1.6;
  margin-bottom: 8px;
  word-break: break-word;
}

.resource-source-url {
  font-size: 12px;
  color: #409eff;
  margin-top: 8px;
}

.resource-source-url a {
  color: #409eff;
  text-decoration: none;
}

.resource-source-url a:hover {
  text-decoration: underline;
}

.resource-image {
  margin-top: 10px;
}

.resource-img {
  max-width: 100%;
  max-height: 200px;
  border-radius: 6px;
  cursor: pointer;
  border: 1px solid #ddd;
}

.no-resources {
  text-align: center;
  color: #909399;
  padding: 40px 20px;
  font-size: 13px;
}

.answer-content .message-text {
  background: transparent;
  padding: 0;
  box-shadow: none;
}

.key-entities {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #e4e7ed;
}

.entities-label {
  font-size: 12px;
  color: #909399;
  margin-bottom: 8px;
}

.entities-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.entity-tag {
  display: inline-block;
  padding: 4px 10px;
  background: #e3f2fd;
  color: #409eff;
  border-radius: 12px;
  font-size: 12px;
}

.sources-info {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #e4e7ed;
}

.sources-label {
  font-size: 12px;
  color: #909399;
  margin-bottom: 8px;
}

.sources-text {
  font-size: 13px;
  color: #606266;
  line-height: 1.6;
}

.message-images {
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
  flex-wrap: wrap;
}

.message-image {
  width: 100px;
  height: 100px;
  object-fit: cover;
  border-radius: 6px;
  cursor: pointer;
  border: 1px solid #ddd;
}

.message-image-result {
  margin-top: 10px;
}

.result-image {
  max-width: 100%;
  max-height: 400px;
  border-radius: 6px;
  cursor: pointer;
  border: 1px solid #ddd;
}

.message-time {
  font-size: 11px;
  color: #999;
  margin-top: 4px;
  text-align: right;
}

.empty-conversation {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #999;
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 12px;
}

.empty-text {
  font-size: 14px;
}

/* 输入区域（页面中部） */
.input-area {
  padding: 20px 30px;
  background: white;
  border-top: 1px solid #eee;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.input-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.mode-switch {
  display: flex;
  gap: 8px;
}

.mode-btn {
  padding: 8px 16px;
  background: #f0f2f5;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  color: #666;
  transition: all 0.3s;
}

.mode-btn:hover {
  background: #e4e7ed;
}

.mode-btn.active {
  background: #409eff;
  color: white;
  border-color: #409eff;
  font-weight: 500;
}

.upload-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  background: #f0f2f5;
  border: 1px dashed #ddd;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  color: #666;
  transition: all 0.3s;
}

.upload-btn:hover {
  background: #e4e7ed;
  border-color: #409eff;
}

.upload-icon {
  font-size: 16px;
}

.uploaded-images {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.uploaded-image-item {
  position: relative;
  width: 80px;
  height: 80px;
}

.preview-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 6px;
  border: 1px solid #ddd;
}

.remove-btn {
  position: absolute;
  top: -8px;
  right: -8px;
  width: 22px;
  height: 22px;
  background: #f56c6c;
  color: white;
  border: none;
  border-radius: 50%;
  cursor: pointer;
  font-size: 14px;
  line-height: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.text-input-section {
  display: flex;
  gap: 12px;
  align-items: flex-end;
}

.text-input {
  flex: 1;
  min-height: 100px;
  max-height: 200px;
  padding: 12px;
  border: 2px solid #e4e7ed;
  border-radius: 8px;
  font-size: 14px;
  font-family: inherit;
  resize: vertical;
  outline: none;
  transition: border-color 0.3s;
}

.text-input:focus {
  border-color: #409eff;
}

.send-btn {
  padding: 12px 28px;
  background: #409eff;
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: background 0.3s;
  white-space: nowrap;
  height: fit-content;
}

.send-btn:hover:not(:disabled) {
  background: #66b1ff;
}

.send-btn:disabled {
  background: #c0c4cc;
  cursor: not-allowed;
}

/* 图片预览模态框 */
.image-preview-modal {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.8);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  cursor: pointer;
}

.preview-modal-image {
  max-width: 90%;
  max-height: 90%;
  object-fit: contain;
  border-radius: 8px;
  cursor: default;
}

/* 滚动条样式 */
.session-list::-webkit-scrollbar,
.conversation-area::-webkit-scrollbar {
  width: 6px;
}

.session-list::-webkit-scrollbar-track,
.conversation-area::-webkit-scrollbar-track {
  background: #f1f1f1;
}

.session-list::-webkit-scrollbar-thumb,
.conversation-area::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 3px;
}

.session-list::-webkit-scrollbar-thumb:hover,
.conversation-area::-webkit-scrollbar-thumb:hover {
  background: #a8a8a8;
}

/* 评论面板样式 */
.comments-panel {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 600px;
  max-width: 90vw;
  max-height: 80vh;
  background: #fff;
  border-radius: 10px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.3);
  z-index: 2000;
  overflow: hidden;
}

.notification-badge {
  position: absolute;
  top: -5px;
  right: -5px;
  background: #f56c6c;
  color: #fff;
  border-radius: 50%;
  width: 20px;
  height: 20px;
  font-size: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
