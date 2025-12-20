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
      <!-- 管理员数据大屏入口 -->
      <div v-if="isAdmin" class="admin-dashboard-link">
        <router-link to="/dashboard" class="dashboard-btn">
          📊 数据大屏
        </router-link>
      </div>
      <div class="search-bar">
        <!-- 支持空输入跳转 -->
        <input 
          type="text" 
          v-model="searchQuery" 
          @keyup.enter="handleSearchFull"
          placeholder="请输入检索词 (例如：寒食节)..." 
        />
        
        <!-- 全文检索入口 -->
        <button class="ai-search-btn" @click="handleSearchFull">
          全文检索
        </button>
        <!-- AI检索入口 -->
        <button class="ai-search-btn" @click="handleSearchAI">
          AI检索
        </button>
      </div>

    </div>
    <!-- ==================== 修改结束：搜索栏 ==================== -->

    <!-- 底部资源卡片 -->
    <div class="resources-section">
      <div class="resource-grid">
        <div 
          class="resource-item" 
          v-for="item in resourceList" 
          :key="item.id"
          @click="goToResourceDetail(item)"
        >
          <div class="res-img-container">
            <!-- 所有资源都应该有图片URL（即使是default图片） -->
            <img 
              :src="item.image_url || '/default.jpg'" 
              class="res-img" 
              @error="handleImageError($event)"
            />
          </div>
          <div class="res-info">
            <h3 class="res-entity-name">{{ item.entity_name }}</h3>
            <p class="res-description">{{ item.description }}</p>
          </div>
        </div>
      </div>
      
      <!-- ==================== 分页控件 ==================== -->
      <div class="pagination" v-if="resourceList.length > 0">
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
import { ref, computed, onMounted, watch } from 'vue';
import { useRouter, useRoute } from 'vue-router';

const router = useRouter();
const route = useRoute();

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

// 1. 获取默认资源列表
const fetchResources = async (page = null) => {
  if (isLoading.value) return;
  isLoading.value = true;
  
  try {
    // 如果没有传入page参数，才从URL中读取
    if (page === null) {
      const urlParams = new URLSearchParams(window.location.search);
      const urlPage = urlParams.get('page');
      if (urlPage && parseInt(urlPage) > 0) {
        page = parseInt(urlPage);
      } else {
        page = 1;
      }
    }
    
    const response = await fetch(`/api/home/resources?page=${page}&page_size=8`);
    
    // 检查响应状态
    if (!response.ok) {
      throw new Error(`HTTP错误! 状态: ${response.status}`);
    }
    
    const data = await response.json();
    
    if (data.success) {
      resourceList.value = data.resources || [];
      currentPage.value = data.pagination?.page || page;
      totalPages.value = data.pagination?.total_pages || 1;
      jumpPage.value = currentPage.value;
      
      // 更新URL中的页码（使用router.push，支持浏览器前进/后退）
      if (currentPage.value > 1) {
        router.push({ 
          path: '/', 
          query: { page: currentPage.value.toString() } 
        }).catch(() => {
          // 忽略导航重复的错误
        });
      } else {
        router.push({ 
          path: '/', 
          query: {} 
        }).catch(() => {
          // 忽略导航重复的错误
        });
      }
      
      // 如果资源列表为空，输出提示
      if (resourceList.value.length === 0) {
        console.warn('资源列表为空，可能是数据库中没有数据');
      }
    } else {
      console.error('获取资源失败:', data.message || '未知错误');
      resourceList.value = [];
    }
  } catch (error) {
    console.error('获取资源失败:', error);
    resourceList.value = [];
    
    // 根据错误类型显示不同的提示信息
    let errorMessage = '无法加载资源列表';
    if (error instanceof TypeError && error.message.includes('fetch')) {
      errorMessage = '无法连接到后端服务，请确认后端服务是否已启动';
    } else if (error.message && error.message.includes('HTTP错误')) {
      errorMessage = `后端服务返回错误：${error.message}`;
    } else {
      errorMessage = `加载失败：${error.message || '未知错误'}，请检查后端服务是否正常运行`;
    }
    
    // 显示用户友好的错误提示
    alert(errorMessage);
  } finally {
    isLoading.value = false;
  }
};

// 2. 处理搜索逻辑 - 跳转到搜索页面
const handleSearchFull = () => {
  const q = searchQuery.value.trim();
  router.push({
    path: '/search',
    query: { q, mode: 'full' }
  });
};

const handleSearchAI = () => {
  const q = searchQuery.value.trim();
  router.push({
    path: '/search',
    query: { q, mode: 'ai' }
  });
};

// 跳转到资源详情页（保存当前页码）
const goToResourceDetail = (item) => {
  const festivalName = item.festival_name || item.entity_name;
  if (festivalName) {
    // 保存当前页码到sessionStorage
    sessionStorage.setItem('lastResourcePage', currentPage.value.toString());
    router.push({
      path: '/resource/detail',
      query: { 
        festival_name: festivalName,
        entity_name: item.entity_name 
      }
    });
  }
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
  // 如果图片加载失败，尝试使用default图片
  if (event.target.src && !event.target.src.includes('/default.jpg')) {
    event.target.src = '/default.jpg';
  } else {
    // 如果default图片也加载失败，显示占位符
    event.target.style.display = 'none';
    // 创建占位符（如果不存在）
    let placeholder = event.target.nextElementSibling;
    if (!placeholder || !placeholder.classList.contains('res-img-placeholder')) {
      placeholder = document.createElement('div');
      placeholder.className = 'res-img-placeholder';
      placeholder.innerHTML = '<span>暂无图片</span>';
      event.target.parentElement.appendChild(placeholder);
    }
    placeholder.style.display = 'flex';
  }
};

// 监听路由变化（处理浏览器前进/后退）
watch(() => route.query.page, (newPage) => {
  if (route.path === '/') {
    const page = newPage ? parseInt(newPage) : 1;
    if (page > 0 && page !== currentPage.value) {
      fetchResources(page);
    }
  }
}, { immediate: false });

// 初始化
onMounted(async () => {
  // 先检查后端服务是否可用
  try {
    const healthResponse = await fetch('/api/health');
    if (!healthResponse.ok) {
      console.warn('后端健康检查失败，状态码:', healthResponse.status);
    } else {
      const healthData = await healthResponse.json();
      console.log('后端服务状态:', healthData);
      if (healthData.database_status && healthData.database_status !== 'connected') {
        console.error('数据库连接状态异常:', healthData.database_status);
      }
    }
  } catch (error) {
    console.error('无法连接到后端服务:', error);
    alert('无法连接到后端服务，请确认后端服务已启动。\n\n请检查：\n1. 后端服务是否正在运行\n2. 查看终端窗口的错误信息\n3. 防火墙设置');
  }
  
  // 加载资源列表（检查URL中的page参数）
  // 初始化时不传入page参数，让fetchResources从URL中读取
  fetchResources();
});
</script>

<style scoped>
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
.ai-search-btn { background-color: #409eff; color: white; border: none; padding: 0 40px; cursor: pointer; font-size: 16px; font-weight: 500; transition: background 0.3s; white-space: nowrap; }
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
  transition: transform 0.3s, box-shadow 0.3s, border-color 0.3s;
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

.admin-dashboard-link {
  text-align: right;
  margin-bottom: 10px;
}

.dashboard-btn {
  display: inline-block;
  padding: 8px 16px;
  background: #409eff;
  color: white;
  text-decoration: none;
  border-radius: 5px;
  font-size: 14px;
  transition: all 0.3s;
}

.dashboard-btn:hover {
  background: #66b1ff;
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(64, 158, 255, 0.3);
}
</style>
