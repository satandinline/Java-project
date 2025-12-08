<template>
  <div class="aigc-container">
    <!-- 顶部论坛入口 -->
    <div class="forum-header">
      <button class="forum-btn" @click="openForum">
        <span class="forum-icon">💬</span>
        论坛
      </button>
    </div>

    <div class="aigc-layout">
      <!-- 左侧：历史会话导航 -->
      <div class="session-nav-panel">
        <div class="session-nav-header">
          <h3>历史会话</h3>
          <button class="new-chat-btn" @click="createNewSession" title="开启新对话">
            <span>+</span>
          </button>
        </div>
        <div class="session-list" ref="sessionListRef">
          <div 
            v-for="(session, index) in sessionHistory" 
            :key="session.id"
            :class="['session-item', { active: currentSessionId === session.id }]"
            @click="loadSession(session.id)"
          >
            <div class="session-title">{{ session.title || `会话 ${index + 1}` }}</div>
            <div class="session-time">{{ formatTime(session.created_at) }}</div>
            <div class="session-preview">{{ getSessionPreview(session) }}</div>
          </div>
          <div v-if="sessionHistory.length === 0" class="empty-sessions">
            暂无历史会话
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
              <span v-if="msg.role === 'user'">👤</span>
              <span v-else>🤖</span>
            </div>
            <div class="message-content-wrapper">
              <div class="message-role-label">{{ msg.role === 'user' ? '用户' : 'AI' }}</div>
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
                      <img :src="msg.image_path" class="result-image" @click="previewImage(msg.image_path)" />
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
                <div class="message-text" v-html="formatAnswerText(msg.content)"></div>
                <div v-if="msg.image_path" class="message-image-result">
                  <img :src="msg.image_path" class="result-image" @click="previewImage(msg.image_path)" />
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
            <label class="upload-btn" v-if="aigcMode === 'image'">
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

// 会话管理
const sessionHistory = ref([]);
const currentSessionId = ref(null);
const currentConversation = ref([]);

// 输入相关
const userInput = ref('');
const uploadedImages = ref([]);
const aigcMode = ref('text'); // 'text' 或 'image'
const isLoading = ref(false);

// UI引用
const sessionListRef = ref(null);
const conversationAreaRef = ref(null);
const previewImageUrl = ref(null);

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
        summary: '新对话'
      })
    });
    
    const data = await response.json();
    if (data.success && data.session) {
      const newSession = {
        id: data.session.id,
        title: data.session.summary || '新对话',
        created_at: data.session.created_at,
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
      // 转换消息格式以匹配前端显示
      currentConversation.value = data.messages.map(msg => ({
        role: msg.role === 'user' ? 'user' : 'assistant',
        content: msg.content,
        timestamp: msg.timestamp,
        retrieved_resources: msg.retrieved_resources,
        key_entities: msg.key_entities || [],
        sources: msg.sources || '',
        image_path: msg.image_path
      }));
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

  // 如果没有当前会话，创建新会话
  if (!currentSessionId.value) {
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
  
  // 保存用户消息到数据库
  if (currentSessionId.value) {
    try {
      await fetch(`/api/aigc/sessions/${currentSessionId.value}/messages`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-Id': currentUser.id.toString()
        },
        body: JSON.stringify({
          sender: 'user',
          content: userMessage.content
        })
      });
    } catch (error) {
      console.error('保存用户消息失败:', error);
    }
  }
  
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

    // 调用后端API（流式模式）
    const formData = new FormData();
    formData.append('query', inputText);
    formData.append('mode', aigcMode.value);
    formData.append('stream', 'true');  // 启用流式输出
    
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

    // 处理流式响应
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';  // 保留最后一个不完整的行

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6));
            
            if (data.type === 'resources') {
              // 收到检索资源信息
              aiMessage.retrieved_resources = data.data;
            } else if (data.type === 'chunk') {
              // 收到文本块，追加到内容
              aiMessage.content += data.data;
              // 实时滚动到底部
              await nextTick();
              scrollToBottom();
            } else if (data.type === 'done') {
              // 收到完整结果
              const finalData = data.data;
              aiMessage.content = finalData.answer || aiMessage.content;
              aiMessage.key_entities = finalData.key_entities || [];
              aiMessage.sources = finalData.sources || '';
              aiMessage.retrieved_resources = finalData.retrieved_resources || aiMessage.retrieved_resources;
              
              // 保存AI消息到数据库
              if (currentSessionId.value) {
                try {
                  await fetch(`/api/aigc/sessions/${currentSessionId.value}/messages`, {
                    method: 'POST',
                    headers: {
                      'Content-Type': 'application/json',
                      'X-User-Id': currentUser.id.toString()
                    },
                    body: JSON.stringify({
                      sender: 'ai',
                      content: aiMessage.content
                    })
                  });
                } catch (error) {
                  console.error('保存AI消息失败:', error);
                }
              }
            }
          } catch (e) {
            console.error('解析流式数据失败:', e, line);
          }
        }
      }
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
      errorContent += '\n\n请确保：\n1. 后端API服务器已启动（运行 python aigc_api_server.py）\n2. 服务器运行在 http://localhost:5000\n3. 检查网络连接';
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

// 打开论坛
const openForum = () => {
  const currentUrl = window.location.href;
  const conversationLink = currentConversation.value.length > 0 
    ? encodeURIComponent(JSON.stringify(currentConversation.value))
    : '';
  
  const forumUrl = conversationLink 
    ? `/forum?conversation=${conversationLink}`
    : '/forum';
  
  window.open(forumUrl, '_blank');
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
        message_count: session.message_count || 0
      }));
    } else {
      console.error('加载会话列表失败:', data.message);
      sessionHistory.value = [];
    }
  } catch (error) {
    console.error('加载会话列表失败:', error);
    sessionHistory.value = [];
  }
};

onMounted(async () => {
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
}

.session-nav-header {
  padding: 15px;
  border-bottom: 1px solid #eee;
  display: flex;
  justify-content: space-between;
  align-items: center;
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
  padding: 40px 20px;
  font-size: 13px;
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
</style>
