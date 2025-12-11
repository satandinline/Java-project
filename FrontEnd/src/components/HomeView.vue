<template>
  <div class="home-container">
    
    <!-- 顶部 3D 轮播区域 (保持不变) -->
    <div class="carousel-section">
      <div class="carousel-stage">
        <div class="card side left" @click="prevSlide">
          <video :src="prevItem.videoSrc" class="cover-video" muted preload="metadata"></video>
          <div class="mask"></div>
        </div>
        <div class="card center">
          <div class="video-box">
            <video :key="currentItem.id" :src="currentItem.videoSrc" autoplay muted controls @ended="handleVideoEnd"></video>
          </div>
        </div>
        <div class="card side right" @click="nextSlide">
          <video :src="nextItem.videoSrc" class="cover-video" muted preload="metadata"></video>
          <div class="mask"></div>
        </div>
      </div>
      <div class="dots">
        <span v-for="(item, index) in mediaList" :key="index" :class="{ active: currentIndex === index }" @click="switchToIndex(index)"></span>
      </div>
    </div>

    <!-- ==================== 修改开始：搜索栏 ==================== -->
    <div class="search-section">
      <div class="search-bar">
        <!-- 1. 绑定 v-model 和回车事件 -->
        <input 
          type="text" 
          v-model="searchQuery" 
          @keyup.enter="handleSearch"
          placeholder="请输入检索词 (例如：寒食节)..." 
        />
        
        <!-- 2. 绑定点击事件，处理加载状态 -->
        <button class="ai-search-btn" @click="handleSearch" :disabled="isSearching">
          {{ isSearching ? '检索中...' : '全文检索' }}
        </button>
      </div>

      <!-- 3. 新增：如果是搜索模式，显示一个返回按钮 -->
      <div v-if="isSearchMode" style="margin-left: 15px;">
        <button class="reset-btn" @click="resetToDefault">
          ✕ 返回全部列表
        </button>
      </div>
    </div>
    <!-- ==================== 修改结束：搜索栏 ==================== -->

    <!-- 底部资源卡片 -->
    <div class="resources-section">
      <!-- 搜索结果为空的提示 -->
      <div v-if="isSearchMode && resourceList.length === 0" style="text-align: center; color: #999; margin-bottom: 30px;">
        未找到与“{{ searchQuery }}”相关的内容
      </div>

      <div class="resource-grid">
        <div class="resource-item" v-for="item in resourceList" :key="item.id">
          <div class="res-img-container">
            <!-- 注意：搜索接口目前可能没有图片，会显示暂无图片 -->
            <img 
              v-if="item.image_url" 
              :src="item.image_url" 
              class="res-img" 
              @error="handleImageError($event)"
            />
            <div v-else class="res-img-placeholder">
              <span>暂无图片</span>
            </div>
          </div>
          <div class="res-info">
            <!-- 搜索结果的 title 会映射到 entity_name -->
            <h3 class="res-entity-name">{{ item.entity_name }}</h3>
            <!-- 搜索结果的 snippet 会映射到 description -->
            <p class="res-description">{{ item.description }}</p>
            
            <!-- 如果是搜索结果，显示来源链接 -->
            <a v-if="item.source_url && isSearchMode" :href="item.source_url" target="_blank" style="font-size: 12px; color: #409eff; margin-top: 10px; display: block;">
              查看来源 &rarr;
            </a>
          </div>
        </div>
      </div>
      
      <!-- ==================== 修改：分页控件 (仅在非搜索模式下显示) ==================== -->
      <div class="pagination" v-if="!isSearchMode && resourceList.length > 0">
        <button class="page-btn" :disabled="currentPage === 1" @click="goToPage(currentPage - 1)">上一页</button>
        <div class="page-numbers">
          <template v-for="pageNum in visiblePages" :key="pageNum">
            <button v-if="pageNum !== '...'" class="page-number" :class="{ active: pageNum === currentPage }" @click="goToPage(pageNum)">{{ pageNum }}</button>
            <span v-else class="page-ellipsis">...</span>
          </template>
        </div>
        <button class="page-btn" :disabled="currentPage === totalPages" @click="goToPage(currentPage + 1)">下一页</button>
        <div class="page-jump">
          <span>跳转到</span>
          <input type="number" v-model.number="jumpPage" :min="1" :max="totalPages" @keyup.enter="jumpToPage" class="page-input" />
          <span>页</span>
          <button class="jump-btn" @click="jumpToPage">确定</button>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';

// --- 轮播图数据 (保持不变) ---
const mediaList = [
  { id: 1, videoSrc: '/videos/v1.mp4' },
  { id: 2, videoSrc: '/videos/v2.mp4' },
  { id: 3, videoSrc: '/videos/v3.mp4' }
];
const currentIndex = ref(0);
const currentItem = computed(() => mediaList[currentIndex.value]);
const prevItem = computed(() => {
  const prevIndex = (currentIndex.value - 1 + mediaList.length) % mediaList.length;
  return mediaList[prevIndex];
});
const nextItem = computed(() => {
  const nextIndex = (currentIndex.value + 1) % mediaList.length;
  return mediaList[nextIndex];
});
const nextSlide = () => currentIndex.value = (currentIndex.value + 1) % mediaList.length;
const prevSlide = () => currentIndex.value = (currentIndex.value - 1 + mediaList.length) % mediaList.length;
const switchToIndex = (index) => currentIndex.value = index;
const handleVideoEnd = () => nextSlide();


// --- 资源列表与搜索逻辑 ---

const resourceList = ref([]);
const currentPage = ref(1);
const totalPages = ref(1);
const jumpPage = ref(1);
const isLoading = ref(false);

// ==================== 新增：搜索相关状态 ====================
const searchQuery = ref('');      // 搜索关键词
const isSearching = ref(false);   // 是否正在请求搜索接口
const isSearchMode = ref(false);  // 是否处于“搜索结果展示模式”

// 1. 获取默认资源列表 (保持原有逻辑，但增加重置搜索模式)
const fetchResources = async (page = 1) => {
  if (isLoading.value) return;
  isLoading.value = true;
  
  try {
    const response = await fetch(`/api/home/resources?page=${page}&page_size=8`);
    const data = await response.json();
    
    if (data.success) {
      resourceList.value = data.resources;
      currentPage.value = data.pagination.page;
      totalPages.value = data.pagination.total_pages;
      jumpPage.value = currentPage.value;
      
      // 确保退出搜索模式
      isSearchMode.value = false;
    } else {
      console.error('获取资源失败:', data.message);
    }
  } catch (error) {
    console.error('获取资源失败:', error);
  } finally {
    isLoading.value = false;
  }
};

// 2. 新增：处理搜索逻辑
const handleSearch = async () => {
  const q = searchQuery.value.trim();
  if (!q) return;

  isSearching.value = true;
  resourceList.value = []; // 先清空列表

  try {
    // 调用 Python 写好的 5000 端口接口
    const response = await fetch(`http://127.0.0.1:5050/api/search?q=${encodeURIComponent(q)}`);
    const resData = await response.json();

    if (resData.code === 200) {
      // 【关键】数据映射：把搜索接口的数据格式，转成卡片需要的格式
      // Python 返回: { title, snippet, tags, source_url }
      // 前端卡片需要: { entity_name, description, image_url }
      resourceList.value = resData.data.map(item => ({
        id: item.id,
        entity_name: item.title,      // 标题 -> 实体名
        description: item.snippet,    // 摘要 -> 描述
        image_url: item.image_url,              // 搜索接口返回的图片URL
        source_url: item.source_url   // 保留来源链接
      }));
      
      // 标记为搜索模式 (隐藏分页)
      isSearchMode.value = true;
    } else {
      alert('搜索出错: ' + resData.msg);
    }
  } catch (error) {
    console.error('搜索请求失败:', error);
    alert('连接搜索服务失败，请确认 search_service.py 已运行');
  } finally {
    isSearching.value = false;
  }
};

// 3. 新增：重置回默认列表
const resetToDefault = () => {
  searchQuery.value = '';
  isSearchMode.value = false;
  fetchResources(1); // 重新加载第一页数据
};

// ==================== 原有分页逻辑 (保持不变) ====================
const goToPage = (page) => {
  if (page >= 1 && page <= totalPages.value && page !== currentPage.value) {
    fetchResources(page);
    window.scrollTo({ top: document.querySelector('.resources-section')?.offsetTop - 100, behavior: 'smooth' });
  }
};

const jumpToPage = () => {
  const page = parseInt(jumpPage.value);
  if (page >= 1 && page <= totalPages.value) {
    goToPage(page);
  } else {
    alert(`请输入1到${totalPages.value}之间的页码`);
    jumpPage.value = currentPage.value;
  }
};

const visiblePages = computed(() => {
  // ... (保持原有的分页计算代码)
  const pages = [];
  const current = currentPage.value;
  const total = totalPages.value;
  if (total <= 7) {
    for (let i = 1; i <= total; i++) pages.push(i);
  } else {
    if (current <= 4) {
      for (let i = 1; i <= 5; i++) pages.push(i);
      pages.push('...'); pages.push(total);
    } else if (current >= total - 3) {
      pages.push(1); pages.push('...');
      for (let i = total - 4; i <= total; i++) pages.push(i);
    } else {
      pages.push(1); pages.push('...');
      for (let i = current - 2; i <= current + 2; i++) pages.push(i);
      pages.push('...'); pages.push(total);
    }
  }
  return pages;
});

const handleImageError = (event) => {
  event.target.style.display = 'none';
  const placeholder = event.target.nextElementSibling;
  if (placeholder) placeholder.style.display = 'flex';
};

// 初始化
onMounted(() => {
  fetchResources(1);
});
</script>

<style scoped>
/* 原有的样式保持不变，只添加一个返回按钮的样式 */
.reset-btn {
  padding: 10px 15px;
  background-color: #f56c6c;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  transition: background 0.3s;
}
.reset-btn:hover {
  background-color: #ff4d4f;
}

.home-container {
  max-width: 1600px;
  margin: 0 auto;
  padding: 30px;
}

/* 轮播区域 */
.carousel-section {
  position: relative;
  height: 500px;
  margin-bottom: 50px;
}

.carousel-stage {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  position: relative;
  gap: 20px;
}

/* 通用卡片样式 */
.card {
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 4px 10px rgba(0,0,0,0.2);
  transition: all 0.5s ease;
  position: relative;
  background: black;
}

/* 中间卡片 */
.card.center {
  width: 65%; 
  height: 450px;
  z-index: 10;
  transform: scale(1);
}

.video-box { width: 100%; height: 100%; }
.video-box video { width: 100%; height: 100%; object-fit: contain; }

/* 两侧卡片 */
.card.side {
  width: 17%;
  height: 350px;
  z-index: 5;
  cursor: pointer;
  opacity: 0.8;
}
.card.side:hover { opacity: 1; transform: scale(1.05); }

/* 改动：侧边视频样式，让它看起来像图片 */
.cover-video {
  width: 100%;
  height: 100%;
  object-fit: cover; /* 关键：让视频画面填满卡片，不留黑边 */
  pointer-events: none; /* 禁止用户在侧边视频上操作（如点击暂停等），点击事件交给父容器处理 */
}

.mask {
  position: absolute; top: 0; left: 0; width: 100%; height: 100%;
  background: rgba(0,0,0,0.3); transition: background 0.3s;
}
.card.side:hover .mask { background: rgba(0,0,0,0); }

.dots { display: flex; justify-content: center; gap: 8px; margin-top: 15px; }
.dots span { width: 12px; height: 12px; border-radius: 50%; background: #ccc; cursor: pointer; transition: all 0.3s; }
.dots span.active { background: #409eff; width: 32px; border-radius: 6px; }

/* 搜索栏 & 底部卡片 (保持不变) */
.search-section { display: flex; justify-content: center; margin: 60px 0; }
.search-bar { display: flex; width: 70%; border: 2px solid #eee; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.05); }
.search-bar input { flex: 1; border: none; padding: 18px 25px; outline: none; background: white; font-size: 16px; }
.ai-search-btn { background-color: #409eff; color: white; border: none; padding: 0 40px; cursor: pointer; font-size: 16px; font-weight: 500; transition: background 0.3s; }
.ai-search-btn:hover { background-color: #66b1ff; }
.ai-search-btn:disabled { background-color: #a0cfff; cursor: not-allowed; }

/* 资源卡片区域 */
.resources-section {
  margin-top: 60px;
}

.resource-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 24px;
  margin-bottom: 40px;
}

.resource-item {
  background: white;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  border: 1px solid #f0f0f0;
  cursor: pointer;
  transition: all 0.3s ease;
  display: flex;
  flex-direction: column;
}

.resource-item:hover {
  transform: translateY(-8px);
  box-shadow: 0 12px 24px rgba(0,0,0,0.15);
  border-color: #409eff;
}

.res-img-container {
  width: 100%;
  height: 240px;
  overflow: hidden;
  background: #f5f7fa;
  position: relative;
}

.res-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.5s ease;
}

.resource-item:hover .res-img {
  transform: scale(1.1);
}

.res-img-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #909399;
  font-size: 14px;
  background: #f5f7fa;
}

.res-info {
  padding: 20px;
  flex: 1;
  display: flex;
  flex-direction: column;
}

.res-entity-name {
  margin: 0 0 12px;
  font-size: 18px;
  color: #303133;
  font-weight: 600;
  transition: color 0.3s;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
}

.resource-item:hover .res-entity-name {
  color: #409eff;
}

.res-description {
  margin: 0;
  font-size: 14px;
  color: #606266;
  line-height: 1.6;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  flex: 1;
}

/* 分页控件 */
.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  margin-top: 40px;
  padding: 20px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.05);
}

.page-btn {
  padding: 8px 16px;
  border: 1px solid #dcdfe6;
  background: white;
  color: #606266;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.3s;
  font-size: 14px;
}

.page-btn:hover:not(:disabled) {
  color: #409eff;
  border-color: #409eff;
}

.page-btn:disabled {
  color: #c0c4cc;
  cursor: not-allowed;
  background: #f5f7fa;
}

.page-numbers {
  display: flex;
  gap: 8px;
  align-items: center;
}

.page-number {
  min-width: 36px;
  height: 36px;
  padding: 0 8px;
  border: 1px solid #dcdfe6;
  background: white;
  color: #606266;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.3s;
  font-size: 14px;
}

.page-number:hover {
  color: #409eff;
  border-color: #409eff;
}

.page-number.active {
  background: #409eff;
  color: white;
  border-color: #409eff;
}

.page-ellipsis {
  padding: 0 4px;
  color: #909399;
}

.page-jump {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: 20px;
  padding-left: 20px;
  border-left: 1px solid #e4e7ed;
  font-size: 14px;
  color: #606266;
}

.page-input {
  width: 60px;
  height: 36px;
  padding: 0 8px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  text-align: center;
  font-size: 14px;
}

.page-input:focus {
  outline: none;
  border-color: #409eff;
}

.jump-btn {
  padding: 8px 16px;
  border: 1px solid #409eff;
  background: #409eff;
  color: white;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.3s;
  font-size: 14px;
}

.jump-btn:hover {
  background: #66b1ff;
  border-color: #66b1ff;
}
</style>