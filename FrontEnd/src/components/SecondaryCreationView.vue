<template>
  <div class="secondary-creation-container">
    <div class="header">
      <h1>✨ 二次创作专区</h1>
      <p class="subtitle">对已有资源进行AI二次创作和编辑</p>
    </div>

    <!-- 资源列表 -->
    <div class="resources-section">
      <div class="section-header">
        <h2>📝 文字AIGC资源</h2>
      </div>
      <div class="resources-grid">
        <div 
          v-for="(resource, index) in textResources" 
          :key="'text-' + index"
          class="resource-card"
          @click="openEditDialog(resource, 'text')"
        >
          <div class="resource-header">
            <span class="resource-type">📝 文字</span>
            <span class="resource-time">{{ formatTime(resource.created_at) }}</span>
          </div>
          <div class="resource-content">
            <h3>{{ resource.title }}</h3>
            <p class="resource-preview">{{ resource.content }}</p>
          </div>
          <div class="resource-footer">
            <button class="edit-btn">编辑</button>
          </div>
        </div>
      </div>
    </div>

    <div class="resources-section">
      <div class="section-header">
        <h2>🎨 图片AIGC资源</h2>
      </div>
      <div class="resources-grid">
        <div 
          v-for="(resource, index) in imageResources" 
          :key="'image-' + index"
          class="resource-card image-card"
          @click="openEditDialog(resource, 'image')"
        >
          <div class="resource-header">
            <span class="resource-type">🎨 图片</span>
            <span class="resource-time">{{ formatTime(resource.created_at) }}</span>
          </div>
          <div class="resource-image">
            <img :src="resource.image_url" :alt="resource.title" />
          </div>
          <div class="resource-content">
            <h3>{{ resource.title }}</h3>
            <p class="resource-preview">{{ resource.description }}</p>
          </div>
          <div class="resource-footer">
            <button class="edit-btn">编辑</button>
          </div>
        </div>
      </div>
    </div>

    <!-- 编辑对话框 -->
    <div v-if="showEditDialog" class="edit-dialog-overlay" @click="closeEditDialog">
      <div class="edit-dialog" @click.stop>
        <div class="dialog-header">
          <h3>编辑资源：{{ currentResource.title }}</h3>
          <button class="close-btn" @click="closeEditDialog">×</button>
        </div>
        
        <div class="dialog-content">
          <!-- 原始内容展示 -->
          <div class="original-content">
            <h4>原始内容</h4>
            <div v-if="currentResourceType === 'text'" class="original-text">
              <p>{{ currentResource.content }}</p>
            </div>
            <div v-else class="original-image">
              <img :src="currentResource.image_url" :alt="currentResource.title" />
              <p>{{ currentResource.description }}</p>
            </div>
          </div>

          <!-- AI对话编辑区域 -->
          <div class="ai-edit-section">
            <h4>AI编辑对话</h4>
            <div class="conversation-area">
              <div 
                v-for="(msg, index) in editConversation" 
                :key="index"
                :class="['message', msg.role]"
              >
                <div class="message-avatar">
                  <img 
                    v-if="msg.role === 'user'" 
                    :src="getAvatarUrl(currentUserInfo?.avatar_path)" 
                    @error="handleAvatarError"
                    alt="用户头像"
                  />
                  <span v-else class="ai-avatar">AI</span>
                </div>
                <div class="message-content">
                  <div class="message-text">{{ msg.content }}</div>
                  <div class="message-time">{{ formatTime(msg.timestamp) }}</div>
                </div>
              </div>
              <div v-if="isEditing" class="message assistant">
                <div class="message-avatar">
                  <span class="ai-avatar">AI</span>
                </div>
                <div class="message-content">
                  <div class="message-text typing">AI正在思考...</div>
                </div>
              </div>
            </div>

            <!-- 输入区域 -->
            <div class="edit-input-area">
              <textarea
                v-model="editInput"
                placeholder="告诉AI您想要如何修改这个资源..."
                class="edit-textarea"
                @keydown.enter.exact.prevent="sendEditMessage"
              ></textarea>
              <button 
                class="send-btn" 
                @click="sendEditMessage"
                :disabled="!editInput.trim() || isEditing"
              >
                发送
              </button>
            </div>
          </div>

          <!-- 编辑后的预览 -->
          <div v-if="editedContent" class="edited-preview">
            <h4>编辑后的内容</h4>
            <div v-if="currentResourceType === 'text'" class="preview-text">
              <p>{{ editedContent }}</p>
            </div>
            <div v-else class="preview-image">
              <img v-if="editedImageUrl" :src="editedImageUrl" alt="编辑后的图片" />
              <p v-if="editedDescription">{{ editedDescription }}</p>
            </div>
            <div class="preview-actions">
              <button class="save-btn" @click="saveEditedContent">保存修改</button>
              <button class="cancel-btn" @click="discardEdit">取消</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { getCurrentUser } from '../utils/api.js';

const router = useRouter();

const currentUserInfo = computed(() => getCurrentUser());

// 模拟数据：文字AIGC资源
const textResources = ref([
  {
    id: 1,
    title: '春节的起源',
    content: '春节，又称农历新年，是中国最重要的传统节日之一。它起源于古代的年兽传说，人们通过放鞭炮、贴春联等方式驱赶年兽，祈求新的一年平安吉祥。春节不仅是一个节日，更是中华民族文化的重要载体，承载着人们对美好生活的向往和祝福。',
    created_at: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString()
  },
  {
    id: 2,
    title: '中秋节的传说',
    content: '中秋节，又称月夕、秋节、仲秋节，是中国传统节日之一。关于中秋节的传说有很多，最著名的是嫦娥奔月的故事。传说后羿射下九个太阳后，得到了一颗不死药，他的妻子嫦娥为了不让坏人得到这颗药，吞下了不死药，飞到了月亮上。从此，人们在中秋节这天赏月、吃月饼，寄托对亲人的思念。',
    created_at: new Date(Date.now() - 5 * 24 * 60 * 60 * 1000).toISOString()
  },
  {
    id: 3,
    title: '端午节的习俗',
    content: '端午节，又称端阳节、龙舟节，是中国传统节日之一。端午节的主要习俗包括：1. 吃粽子：用糯米包裹各种馅料，用竹叶包裹煮熟。2. 赛龙舟：人们划龙舟比赛，纪念屈原。3. 挂艾草：在门口挂艾草和菖蒲，驱邪避疫。4. 饮雄黄酒：传说可以驱邪避疫。这些习俗都体现了中华民族的文化传统和智慧。',
    created_at: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString()
  }
]);

// 模拟数据：图片AIGC资源
const imageResources = ref([
  {
    id: 1,
    title: '春节场景图',
    description: '一幅描绘春节热闹场景的图片，展现了人们贴春联、放鞭炮、包饺子的传统习俗。',
    image_url: '/default.jpg',
    created_at: new Date(Date.now() - 1 * 24 * 60 * 60 * 1000).toISOString()
  },
  {
    id: 2,
    title: '中秋月圆图',
    description: '一幅描绘中秋月圆之夜的图片，展现了家人团聚、赏月、吃月饼的温馨场景。',
    image_url: '/default.jpg',
    created_at: new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString()
  },
  {
    id: 3,
    title: '端午龙舟图',
    description: '一幅描绘端午节赛龙舟的图片，展现了人们划龙舟比赛的激烈场面和节日氛围。',
    image_url: '/default.jpg',
    created_at: new Date(Date.now() - 6 * 24 * 60 * 60 * 1000).toISOString()
  }
]);

// 编辑对话框相关
const showEditDialog = ref(false);
const currentResource = ref(null);
const currentResourceType = ref('text');
const editConversation = ref([]);
const editInput = ref('');
const isEditing = ref(false);
const editedContent = ref('');
const editedImageUrl = ref('');
const editedDescription = ref('');

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

// 打开编辑对话框
const openEditDialog = (resource, type) => {
  currentResource.value = resource;
  currentResourceType.value = type;
  editConversation.value = [];
  editInput.value = '';
  editedContent.value = '';
  editedImageUrl.value = '';
  editedDescription.value = '';
  showEditDialog.value = true;
};

// 关闭编辑对话框
const closeEditDialog = () => {
  showEditDialog.value = false;
  currentResource.value = null;
  editConversation.value = [];
  editInput.value = '';
  editedContent.value = '';
  editedImageUrl.value = '';
  editedDescription.value = '';
};

// 发送编辑消息
const sendEditMessage = async () => {
  if (!editInput.value.trim() || isEditing.value) return;

  const userMessage = {
    role: 'user',
    content: editInput.value,
    timestamp: new Date().toISOString()
  };

  editConversation.value.push(userMessage);
  const userInputText = editInput.value;
  editInput.value = '';
  isEditing.value = true;

  try {
    // 调用AI编辑API
    const response = await fetch('/api/aigc/edit-resource', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-User-Id': currentUserInfo.value?.id?.toString() || ''
      },
      body: JSON.stringify({
        resource_id: currentResource.value.id,
        resource_type: currentResourceType.value,
        original_content: currentResourceType.value === 'text' 
          ? currentResource.value.content 
          : currentResource.value.description,
        edit_request: userInputText
      })
    });

    const data = await response.json();
    
    if (data.success) {
      const aiMessage = {
        role: 'assistant',
        content: data.message || '已根据您的要求修改了资源内容。',
        timestamp: new Date().toISOString()
      };
      editConversation.value.push(aiMessage);

      // 更新编辑后的内容
      if (currentResourceType.value === 'text') {
        editedContent.value = data.edited_content || currentResource.value.content;
      } else {
        editedImageUrl.value = data.edited_image_url || currentResource.value.image_url;
        editedDescription.value = data.edited_description || currentResource.value.description;
      }
    } else {
      const errorMessage = {
        role: 'assistant',
        content: data.message || '编辑失败，请稍后重试。',
        timestamp: new Date().toISOString()
      };
      editConversation.value.push(errorMessage);
    }
  } catch (error) {
    const errorMessage = {
      role: 'assistant',
      content: '编辑失败，请检查网络连接后重试。',
      timestamp: new Date().toISOString()
    };
    editConversation.value.push(errorMessage);
  } finally {
    isEditing.value = false;
  }
};

// 保存编辑后的内容
const saveEditedContent = async () => {
  try {
    const response = await fetch('/api/aigc/save-edited-resource', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-User-Id': currentUserInfo.value?.id?.toString() || ''
      },
      body: JSON.stringify({
        resource_id: currentResource.value.id,
        resource_type: currentResourceType.value,
        edited_content: currentResourceType.value === 'text' ? editedContent.value : editedDescription.value,
        edited_image_url: currentResourceType.value === 'image' ? editedImageUrl.value : null
      })
    });

    const data = await response.json();
    if (data.success) {
      alert('保存成功！');
      // 更新资源列表
      if (currentResourceType.value === 'text') {
        const index = textResources.value.findIndex(r => r.id === currentResource.value.id);
        if (index !== -1) {
          textResources.value[index].content = editedContent.value;
        }
      } else {
        const index = imageResources.value.findIndex(r => r.id === currentResource.value.id);
        if (index !== -1) {
          imageResources.value[index].description = editedDescription.value;
          if (editedImageUrl.value) {
            imageResources.value[index].image_url = editedImageUrl.value;
          }
        }
      }
      closeEditDialog();
    } else {
      alert('保存失败：' + (data.message || '未知错误'));
    }
  } catch (error) {
    alert('保存失败，请稍后重试');
  }
};

// 放弃编辑
const discardEdit = () => {
  editedContent.value = '';
  editedImageUrl.value = '';
  editedDescription.value = '';
};

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

onMounted(() => {
  // 可以在这里加载真实的资源数据
});
</script>

<style scoped>
.secondary-creation-container {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
  background: #f5f7fa;
  min-height: calc(100vh - 60px);
}

.header {
  text-align: center;
  margin-bottom: 30px;
}

.header h1 {
  font-size: 32px;
  color: #333;
  margin-bottom: 10px;
}

.subtitle {
  color: #666;
  font-size: 16px;
}

.resources-section {
  margin-bottom: 40px;
}

.section-header {
  margin-bottom: 20px;
}

.section-header h2 {
  font-size: 24px;
  color: #333;
  border-bottom: 2px solid #409eff;
  padding-bottom: 10px;
}

.resources-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;
}

.resource-card {
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
}

.resource-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.resource-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.resource-type {
  font-size: 14px;
  color: #409eff;
  font-weight: bold;
}

.resource-time {
  font-size: 12px;
  color: #999;
}

.resource-content h3 {
  font-size: 18px;
  color: #333;
  margin-bottom: 10px;
}

.resource-preview {
  color: #666;
  font-size: 14px;
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.resource-image {
  margin-bottom: 15px;
}

.resource-image img {
  width: 100%;
  height: 200px;
  object-fit: cover;
  border-radius: 4px;
}

.resource-footer {
  margin-top: 15px;
  text-align: right;
}

.edit-btn {
  padding: 6px 16px;
  background: #409eff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
}

.edit-btn:hover {
  background: #66b1ff;
}

/* 编辑对话框样式 */
.edit-dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}

.edit-dialog {
  background: white;
  border-radius: 8px;
  width: 90%;
  max-width: 900px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.dialog-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  border-bottom: 1px solid #eee;
}

.dialog-header h3 {
  margin: 0;
  color: #333;
}

.close-btn {
  background: none;
  border: none;
  font-size: 24px;
  color: #999;
  cursor: pointer;
  padding: 0;
  width: 30px;
  height: 30px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.close-btn:hover {
  color: #333;
}

.dialog-content {
  padding: 20px;
  overflow-y: auto;
  flex: 1;
}

.original-content {
  margin-bottom: 30px;
  padding: 15px;
  background: #f5f7fa;
  border-radius: 4px;
}

.original-content h4 {
  margin-top: 0;
  margin-bottom: 10px;
  color: #333;
}

.original-text p {
  color: #666;
  line-height: 1.6;
}

.original-image img {
  max-width: 100%;
  border-radius: 4px;
  margin-bottom: 10px;
}

.ai-edit-section {
  margin-bottom: 30px;
}

.ai-edit-section h4 {
  margin-top: 0;
  margin-bottom: 15px;
  color: #333;
}

.conversation-area {
  max-height: 400px;
  overflow-y: auto;
  padding: 15px;
  background: #f9f9f9;
  border-radius: 4px;
  margin-bottom: 15px;
}

.message {
  display: flex;
  margin-bottom: 15px;
}

.message.user {
  flex-direction: row-reverse;
}

.message-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  overflow: hidden;
  margin: 0 10px;
  flex-shrink: 0;
}

.message-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.ai-avatar {
  width: 40px;
  height: 40px;
  background: #409eff;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  font-weight: bold;
}

.message-content {
  flex: 1;
  max-width: 70%;
}

.message.user .message-content {
  text-align: right;
}

.message-text {
  padding: 10px 15px;
  border-radius: 8px;
  background: white;
  color: #333;
  line-height: 1.5;
}

.message.user .message-text {
  background: #409eff;
  color: white;
}

.message-text.typing {
  color: #999;
  font-style: italic;
}

.message-time {
  font-size: 12px;
  color: #999;
  margin-top: 5px;
}

.edit-input-area {
  display: flex;
  gap: 10px;
}

.edit-textarea {
  flex: 1;
  padding: 10px;
  border: 1px solid #ddd;
  border-radius: 4px;
  resize: none;
  font-size: 14px;
  min-height: 60px;
}

.edit-textarea:focus {
  outline: none;
  border-color: #409eff;
}

.send-btn {
  padding: 10px 20px;
  background: #409eff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
}

.send-btn:hover:not(:disabled) {
  background: #66b1ff;
}

.send-btn:disabled {
  background: #ccc;
  cursor: not-allowed;
}

.edited-preview {
  padding: 15px;
  background: #e8f5e9;
  border-radius: 4px;
  border: 1px solid #4caf50;
}

.edited-preview h4 {
  margin-top: 0;
  margin-bottom: 10px;
  color: #333;
}

.preview-text p {
  color: #666;
  line-height: 1.6;
}

.preview-image img {
  max-width: 100%;
  border-radius: 4px;
  margin-bottom: 10px;
}

.preview-actions {
  margin-top: 15px;
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}

.save-btn {
  padding: 8px 20px;
  background: #4caf50;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.save-btn:hover {
  background: #66bb6a;
}

.cancel-btn {
  padding: 8px 20px;
  background: #999;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.cancel-btn:hover {
  background: #aaa;
}
</style>

