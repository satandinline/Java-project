<template>
  <div class="mm-page">
    <div class="mm-header">
      <div>
        <div class="mm-title">图文互搜</div>
        <div class="mm-subtitle">输入文本或上传图片，检索相关文本/图片资源</div>
      </div>
    </div>

    <div class="mm-inputs">
      <textarea
        v-model="mmQuery"
        class="text-input"
        rows="4"
        placeholder="请输入要检索的文本，或上传图片进行以图搜文/图"
      ></textarea>
      <div class="mm-actions">
        <button
          class="send-btn"
          @click="performMultimodalSearch"
          :disabled="mmLoading || (!mmQuery.trim() && mmUploadedImages.length === 0)"
        >
          <span v-if="mmLoading">检索中...</span>
          <span v-else>开始互搜</span>
        </button>
        <button
          class="upload-btn inline-upload push-right"
          @click="() => $refs.mmImageInput && $refs.mmImageInput.click()"
        >
          上传图片
        </button>
        <input
          ref="mmImageInput"
          type="file"
          accept="image/*"
          multiple
          @change="handleMMImageUpload"
          style="display: none;"
        />
      </div>
    </div>

    <div v-if="mmUploadedImages.length > 0" class="uploaded-images mm">
      <div
        v-for="(item, index) in mmUploadedImages"
        :key="index"
        class="uploaded-image-item"
      >
        <img :src="item.preview" class="preview-img" />
        <button class="remove-btn" @click="removeMMImage(index)">×</button>
      </div>
    </div>

    <div v-if="mmError" class="mm-error">{{ mmError }}</div>

    <div v-if="mmResults" class="mm-results">
      <div class="mm-meta">
        <div>使用的查询：{{ mmResults.query_used }}</div>
        <div v-if="mmResults.image_descriptions?.length">
          图片描述：{{ mmResults.image_descriptions.join('；') }}
        </div>
      </div>

      <div class="mm-columns">
        <!-- 列①：向量结果 -->
        <div class="mm-card mm-card-vector">
          <div class="mm-card-title">🔍 向量结果</div>
          <div v-if="mmResults.vector_results?.length" class="mm-results-list">
            <div
              v-for="(item, idx) in mmResults.vector_results"
              :key="idx"
              class="mm-item mm-item-clickable"
              @click="goToResourceDetail(item)"
            >
              <div class="mm-title">{{ item.title || '向量检索结果' }}</div>
              <div class="mm-text">{{ item.content }}</div>
              <div class="mm-meta-line">来源: {{ item.source || item.table || '向量库' }}</div>
            </div>
          </div>
          <div v-else class="mm-empty">暂无向量结果</div>
        </div>

        <!-- 列②：文字结果 -->
        <div class="mm-card mm-card-text">
          <div class="mm-card-title">📝 文字结果</div>
          <div v-if="mmResults.text_results?.length" class="mm-results-list">
            <div
              v-for="(item, idx) in mmResults.text_results"
              :key="idx"
              class="mm-item mm-item-clickable"
              @click="goToResourceDetail(item)"
            >
              <div class="mm-title">{{ item.title || item.table || '记录' }}</div>
              <div class="mm-text">{{ item.content }}</div>
              <div class="mm-meta-line">来源: {{ item.source || item.table || '数据库' }}</div>
            </div>
          </div>
          <div v-else class="mm-empty">暂无文字结果</div>
        </div>

        <!-- 列③：图片结果 -->
        <div class="mm-card mm-card-image">
          <div class="mm-card-title">🖼️ 图片结果</div>
          <div v-if="mmResults.image_results?.length" class="mm-results-list">
            <div
              v-for="(item, idx) in mmResults.image_results"
              :key="idx"
              class="mm-item mm-item-clickable"
              @click="goToResourceDetail(item)"
            >
              <div v-if="item.image_url" class="mm-image">
                <img
                  :src="getImageUrl(item.image_url)"
                  class="mm-img"
                  @click.stop="previewImage(getImageUrl(item.image_url))"
                />
              </div>
              <div class="mm-title">{{ item.title || '未命名' }}</div>
              <div class="mm-text">{{ item.content || '' }}</div>
              <div class="mm-meta-line">来源: {{ item.source || item.table || '数据库' }}</div>
            </div>
          </div>
          <div v-else class="mm-empty">暂无图片结果</div>
        </div>
      </div>
    </div>

    <div v-if="previewImageUrl" class="image-preview-modal" @click="previewImageUrl = null">
      <img :src="previewImageUrl" class="preview-modal-image" @click.stop />
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { getCurrentUser } from '../utils/api.js';

const router = useRouter();

const mmQuery = ref('');
const mmUploadedImages = ref([]);
const mmResults = ref(null);
const mmLoading = ref(false);
const mmError = ref('');
const previewImageUrl = ref(null);

const handleMMImageUpload = (event) => {
  const files = event.target.files;
  if (files && files.length > 0) {
    Array.from(files).forEach(file => {
      if (file.type.startsWith('image/')) {
        const reader = new FileReader();
        reader.onload = (e) => {
          mmUploadedImages.value.push({ file, preview: e.target.result });
        };
        reader.readAsDataURL(file);
      }
    });
  }
};

const removeMMImage = (index) => {
  mmUploadedImages.value.splice(index, 1);
};

const performMultimodalSearch = async () => {
  if (mmLoading.value) return;
  const queryText = mmQuery.value.trim();
  if (!queryText && mmUploadedImages.value.length === 0) {
    alert('请输入查询文本或上传图片');
    return;
  }

  const currentUser = getCurrentUser();
  if (!currentUser || !currentUser.id) {
    alert('请先登录');
    return;
  }

  mmLoading.value = true;
  mmError.value = '';
  mmResults.value = null;

  const formData = new FormData();
  formData.append('mode', 'text');
  formData.append('query', queryText);
  formData.append('user_id', currentUser.id);
  mmUploadedImages.value.forEach((item) => {
    formData.append('images', item.file);
  });

  try {
    const resp = await fetch('/api/multimodal/search', {
      method: 'POST',
      headers: {
        'X-User-Id': currentUser.id.toString()
      },
      body: formData
    });
    const text = await resp.text();
    let data = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch (parseErr) {
      mmError.value = '后端返回非JSON，请检查服务器日志';
      return;
    }
    if (!resp.ok || !data || data.success === false) {
      mmError.value = data?.message || '检索失败';
      return;
    }
    mmResults.value = data;
  } catch (err) {
    mmError.value = err?.message || '请求失败';
  } finally {
    mmLoading.value = false;
  }
};

const previewImage = (url) => {
  previewImageUrl.value = url;
};

// 获取图片URL
const getImageUrl = (url) => {
  if (!url) return '/default.jpg';
  if (url.startsWith('http://') || url.startsWith('https://')) {
    return url;
  }
  if (url.startsWith('/')) {
    return url;
  }
  if (url.includes('crawled_images')) {
    const fileName = url.split('/').pop();
    return `/api/images/crawled/${fileName}`;
  }
  if (url.includes('AIGC_graph')) {
    const fileName = url.split('/').pop();
    return `/api/images/aigc/${fileName}`;
  }
  return url;
};

// 跳转到资源详情页
const goToResourceDetail = (item) => {
  if (!item.id) {
    return;
  }
  
  // 如果有table参数，使用id+table方式
  if (item.table) {
    const query = {
      id: item.id,
      table: item.table,
      resource_type: item.resource_type || '',
      entity_name: item.title || ''
    };
    router.push({
      path: '/resource/detail',
      query: query
    });
  } else if (item.title || item.entity_name) {
    // 否则使用festival_name方式
    router.push({
      path: '/resource/detail',
      query: {
        festival_name: item.title || item.entity_name || ''
      }
    });
  } else {
  }
};
</script>

<style scoped>
.mm-page {
  max-width: 1200px;
  margin: 20px auto;
  padding: 20px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 6px 20px rgba(0,0,0,0.06);
}
.mm-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.mm-title {
  font-size: 20px;
  font-weight: 700;
  color: #222;
}
.mm-subtitle {
  font-size: 13px;
  color: #666;
  margin-top: 4px;
}
.mm-mode { gap: 8px; }
.mode-btn {
  padding: 8px 14px;
  border: 1px solid #dcdfe6;
  border-radius: 8px;
  background: #f7f9fc;
  cursor: pointer;
  font-size: 13px;
}
.mode-btn.active {
  background: #e8f3ff;
  color: #409eff;
  border-color: #409eff;
}
.upload-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  border: 1px dashed #dcdfe6;
  border-radius: 8px;
  cursor: pointer;
  background: #fafafa;
}
.upload-icon { font-size: 14px; }
.mm-inputs {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.text-input {
  border: 1px solid #dcdfe6;
  border-radius: 10px;
  padding: 12px;
  resize: vertical;
  font-size: 14px;
  min-height: 120px;
}
.mm-actions {
  display: flex;
  justify-content: flex-start;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}
.send-btn {
  min-width: 120px;
  height: 44px;
  background: linear-gradient(135deg, #409eff, #66b1ff);
  border: none;
  color: #fff;
  border-radius: 10px;
  cursor: pointer;
  font-weight: 600;
  padding: 0 18px;
  align-self: flex-start;
  font-size: 14px;
  line-height: 1;
}
.send-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.uploaded-images.mm {
  display: flex;
  gap: 10px;
  margin: 12px 0;
  flex-wrap: wrap;
}
.uploaded-image-item {
  position: relative;
  width: 100px;
  height: 100px;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}
.preview-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.remove-btn {
  position: absolute;
  top: 4px;
  right: 4px;
  background: rgba(0,0,0,0.6);
  color: #fff;
  border: none;
  border-radius: 50%;
  width: 20px;
  height: 20px;
  cursor: pointer;
}
.mm-error {
  color: #e74c3c;
  margin: 8px 0;
}
.inline-upload {
  min-width: 120px;
  height: 44px;
  background: linear-gradient(135deg, #409eff, #66b1ff);
  border: none;
  color: #fff;
  border-radius: 10px;
  cursor: pointer;
  font-weight: 600;
  padding: 0 18px;
  font-size: 14px;
  line-height: 44px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  text-align: center;
}
.push-right {
  margin-left: auto;
}
.mm-results {
  margin-top: 16px;
}
.mm-meta {
  font-size: 13px;
  color: #555;
  margin-bottom: 10px;
}
.mm-columns {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 20px;
}

.mm-card-vector {
  border-left: 4px solid #409eff;
}

.mm-card-text {
  border-left: 4px solid #67c23a;
}

.mm-card-image {
  border-left: 4px solid #e6a23c;
}
.mm-card {
  background: #f9fbff;
  border: 1px solid #e6ecf5;
  border-radius: 10px;
  padding: 12px;
}
.mm-card-title {
  font-weight: 600;
  margin-bottom: 8px;
}
.mm-item {
  padding: 10px;
  border-radius: 8px;
  background: #fff;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.6);
  margin-bottom: 10px;
}

.mm-item-clickable {
  cursor: pointer;
  transition: all 0.2s;
}

.mm-item-clickable:hover {
  background: #f0f9ff;
  box-shadow: 0 2px 8px rgba(64, 158, 255, 0.2);
  transform: translateY(-2px);
}

.mm-results-list {
  max-height: 600px;
  overflow-y: auto;
}
.mm-title { font-weight: 600; margin-bottom: 4px; }
.mm-text { color: #333; }
.mm-meta-line { font-size: 12px; color: #777; margin-top: 4px; }
.mm-image { margin-top: 6px; }
.mm-img {
  max-width: 100%;
  border-radius: 6px;
  cursor: pointer;
}
.mm-empty {
  color: #999;
  font-size: 13px;
}
.image-preview-modal {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}
.preview-modal-image {
  max-width: 90vw;
  max-height: 90vh;
  border-radius: 8px;
  box-shadow: 0 10px 30px rgba(0,0,0,0.4);
}
</style>

