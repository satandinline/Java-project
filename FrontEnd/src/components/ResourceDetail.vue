<template>
  <div class="resource-detail-container">
    <!-- 返回按钮 -->
    <div class="back-section">
      <button class="back-btn" @click="goBack">
        ← 返回首页
      </button>
    </div>

    <!-- 资源信息 -->
    <div class="resource-header" v-if="resourceInfo">
      <h1 class="festival-name">{{ resourceInfo.festival_name || resourceInfo.entity_name }}</h1>
      <p class="resource-description" v-if="resourceInfo.description && resourceInfo.description !== '暂无简介'">
        {{ resourceInfo.description }}
      </p>
      <p class="resource-description" v-else style="color: #999; font-style: italic;">
        暂无简介
      </p>
      <div class="resource-meta">
        <span class="meta-item">共 {{ resourceInfo.total_images || 0 }} 张图片</span>
      </div>
    </div>

    <!-- 加载状态 -->
    <div v-if="isLoading" class="loading-section">
      <p>正在加载资源详情...</p>
    </div>

    <!-- 错误提示 -->
    <div v-if="error" class="error-section">
      <p class="error-message">{{ error }}</p>
      <button class="retry-btn" @click="loadResourceDetail">重试</button>
    </div>

    <!-- 图片网格 -->
    <div v-if="!isLoading && !error && imageList.length > 0" class="images-grid">
      <div 
        v-for="(image, index) in imageList" 
        :key="image.id || index"
        class="image-item"
        @click="openImageModal(image, index)"
      >
        <div class="image-wrapper">
          <img 
            :src="image.image_url" 
            :alt="`${resourceInfo?.festival_name || '资源'} - 图片 ${index + 1}`"
            class="detail-image"
            @error="handleImageError($event)"
            loading="lazy"
          />
          <div class="image-overlay">
            <span class="image-index">图片 {{ index + 1 }}</span>
          </div>
        </div>
        <div class="image-info" v-if="image.dimensions">
          <span class="image-dimensions">{{ image.dimensions }}</span>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-if="!isLoading && !error && imageList.length === 0" class="empty-section">
      <p>该资源暂无图片</p>
    </div>

    <!-- 图片预览模态框 -->
    <div v-if="showImageModal" class="image-modal" @click="closeImageModal">
      <div class="modal-content" @click.stop>
        <button class="modal-close" @click="closeImageModal">×</button>
        <button class="modal-nav modal-prev" @click="prevImage" v-if="currentImageIndex > 0">‹</button>
        <button class="modal-nav modal-next" @click="nextImage" v-if="currentImageIndex < imageList.length - 1">›</button>
        <img 
          :src="currentImage?.image_url" 
          :alt="`${resourceInfo?.festival_name || '资源'} - 图片 ${currentImageIndex + 1}`"
          class="modal-image"
          @error="handleImageError($event)"
        />
        <div class="modal-info">
          <span class="modal-counter">{{ currentImageIndex + 1 }} / {{ imageList.length }}</span>
          <span class="modal-filename" v-if="currentImage?.file_name">{{ currentImage.file_name }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue';
import { useRouter, useRoute } from 'vue-router';

const router = useRouter();
const route = useRoute();

const resourceInfo = ref(null);
const imageList = ref([]);
const isLoading = ref(false);
const error = ref(null);

const showImageModal = ref(false);
const currentImageIndex = ref(0);
const currentImage = computed(() => imageList.value[currentImageIndex.value] || null);

// 加载资源详情
const loadResourceDetail = async () => {
  const festivalName = route.query.festival_name || route.query.entity_name;
  if (!festivalName) {
    error.value = '缺少资源名称参数';
    return;
  }

  isLoading.value = true;
  error.value = null;

  try {
    const response = await fetch(`/api/resource/detail?festival_name=${encodeURIComponent(festivalName)}`);
    
    if (!response.ok) {
      throw new Error(`HTTP错误! 状态: ${response.status}`);
    }

    const data = await response.json();

    if (data.success) {
      resourceInfo.value = {
        festival_name: data.festival_name,
        entity_name: data.entity_name,
        description: data.description,
        total_images: data.total_images
      };
      imageList.value = data.images || [];
    } else {
      error.value = data.message || '获取资源详情失败';
    }
  } catch (err) {
    console.error('获取资源详情失败:', err);
    error.value = `加载失败：${err.message || '未知错误'}`;
  } finally {
    isLoading.value = false;
  }
};

// 返回首页（恢复之前的页码）
const goBack = () => {
  const lastPage = sessionStorage.getItem('lastResourcePage');
  if (lastPage) {
    router.push({
      path: '/',
      query: { page: lastPage }
    });
    // 清除保存的页码
    sessionStorage.removeItem('lastResourcePage');
  } else {
    router.push('/');
  }
};

// 打开图片预览
const openImageModal = (image, index) => {
  currentImageIndex.value = index;
  showImageModal.value = true;
  document.body.style.overflow = 'hidden'; // 禁止背景滚动
};

// 关闭图片预览
const closeImageModal = () => {
  showImageModal.value = false;
  document.body.style.overflow = ''; // 恢复滚动
};

// 上一张图片
const prevImage = () => {
  if (currentImageIndex.value > 0) {
    currentImageIndex.value--;
  }
};

// 下一张图片
const nextImage = () => {
  if (currentImageIndex.value < imageList.value.length - 1) {
    currentImageIndex.value++;
  }
};

// 键盘导航
const handleKeydown = (e) => {
  if (!showImageModal.value) return;
  
  if (e.key === 'ArrowLeft') {
    prevImage();
  } else if (e.key === 'ArrowRight') {
    nextImage();
  } else if (e.key === 'Escape') {
    closeImageModal();
  }
};

// 图片加载错误处理
const handleImageError = (event) => {
  event.target.src = '/default.jpg'; // 使用默认图片
};

onMounted(() => {
  loadResourceDetail();
  window.addEventListener('keydown', handleKeydown);
});

// 组件卸载时移除事件监听
onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown);
  document.body.style.overflow = ''; // 确保恢复滚动
});
</script>

<style scoped>
.resource-detail-container {
  min-height: 100vh;
  padding: 20px;
  max-width: 1400px;
  margin: 0 auto;
  background: #f5f5f5;
}

.back-section {
  margin-bottom: 20px;
}

.back-btn {
  padding: 10px 20px;
  background: #fff;
  border: 1px solid #ddd;
  border-radius: 5px;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.3s;
}

.back-btn:hover {
  background: #f0f0f0;
  border-color: #999;
}

.resource-header {
  background: #fff;
  padding: 30px;
  border-radius: 10px;
  margin-bottom: 30px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.festival-name {
  font-size: 32px;
  color: #333;
  margin: 0 0 15px 0;
  font-weight: bold;
}

.resource-description {
  font-size: 16px;
  color: #666;
  line-height: 1.6;
  margin: 0 0 15px 0;
}

.resource-meta {
  display: flex;
  gap: 20px;
  margin-top: 15px;
}

.meta-item {
  font-size: 14px;
  color: #999;
}

.loading-section,
.error-section,
.empty-section {
  text-align: center;
  padding: 60px 20px;
  background: #fff;
  border-radius: 10px;
  margin-bottom: 30px;
}

.error-message {
  color: #e74c3c;
  margin-bottom: 20px;
}

.retry-btn {
  padding: 10px 20px;
  background: #3498db;
  color: #fff;
  border: none;
  border-radius: 5px;
  cursor: pointer;
  font-size: 14px;
}

.retry-btn:hover {
  background: #2980b9;
}

.images-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 20px;
  margin-bottom: 30px;
}

.image-item {
  background: #fff;
  border-radius: 10px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  cursor: pointer;
  transition: transform 0.3s, box-shadow 0.3s;
}

.image-item:hover {
  transform: translateY(-5px);
  box-shadow: 0 4px 16px rgba(0,0,0,0.2);
}

.image-wrapper {
  position: relative;
  width: 100%;
  padding-top: 75%; /* 4:3 比例 */
  overflow: hidden;
  background: #f0f0f0;
}

.detail-image {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.image-overlay {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  background: linear-gradient(to top, rgba(0,0,0,0.7), transparent);
  padding: 10px;
  opacity: 0;
  transition: opacity 0.3s;
}

.image-item:hover .image-overlay {
  opacity: 1;
}

.image-index {
  color: #fff;
  font-size: 14px;
}

.image-info {
  padding: 10px;
  font-size: 12px;
  color: #999;
}

.image-dimensions {
  display: block;
}

/* 图片预览模态框 */
.image-modal {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.9);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.modal-content {
  position: relative;
  max-width: 90%;
  max-height: 90%;
  cursor: default;
}

.modal-close {
  position: absolute;
  top: -40px;
  right: 0;
  background: transparent;
  border: none;
  color: #fff;
  font-size: 40px;
  cursor: pointer;
  width: 40px;
  height: 40px;
  line-height: 40px;
  z-index: 1001;
}

.modal-close:hover {
  opacity: 0.7;
}

.modal-nav {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  background: rgba(255, 255, 255, 0.3);
  border: none;
  color: #fff;
  font-size: 50px;
  cursor: pointer;
  width: 60px;
  height: 60px;
  line-height: 60px;
  border-radius: 50%;
  z-index: 1001;
  transition: background 0.3s;
}

.modal-nav:hover {
  background: rgba(255, 255, 255, 0.5);
}

.modal-prev {
  left: -80px;
}

.modal-next {
  right: -80px;
}

.modal-image {
  max-width: 100%;
  max-height: 80vh;
  object-fit: contain;
  display: block;
}

.modal-info {
  position: absolute;
  bottom: -50px;
  left: 50%;
  transform: translateX(-50%);
  color: #fff;
  text-align: center;
}

.modal-counter {
  display: block;
  font-size: 16px;
  margin-bottom: 5px;
}

.modal-filename {
  display: block;
  font-size: 12px;
  opacity: 0.7;
}

@media (max-width: 768px) {
  .images-grid {
    grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
    gap: 15px;
  }

  .modal-nav {
    width: 40px;
    height: 40px;
    font-size: 30px;
    line-height: 40px;
  }

  .modal-prev {
    left: 10px;
  }

  .modal-next {
    right: 10px;
  }
}
</style>

