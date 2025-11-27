<template>
  <div class="home-container">
    
    <!-- 顶部 3D 轮播区域 -->
    <div class="carousel-section">
      <div class="carousel-stage">
        
        <!-- 左侧：显示上一条视频的【第一帧】 -->
        <div class="card side left" @click="prevSlide">
          <!-- 改动：这里以前是 img，现在改成 video -->
          <!-- muted: 静音 (防止意外播放声音) -->
          <!-- preload="metadata": 预加载元数据，让浏览器显示第一帧 -->
          <video 
            :src="prevItem.videoSrc" 
            class="cover-video" 
            muted 
            preload="metadata"
          ></video>
          <div class="mask"></div>
        </div>

        <!-- 中间：正在播放的视频 -->
        <div class="card center">
          <div class="video-box">
            <video 
              :key="currentItem.id" 
              :src="currentItem.videoSrc" 
              autoplay 
              muted 
              controls
              @ended="handleVideoEnd"
            ></video>
          </div>
        </div>

        <!-- 右侧：显示下一条视频的【第一帧】 -->
        <div class="card side right" @click="nextSlide">
          <!-- 改动：同左侧，改成 video -->
          <video 
            :src="nextItem.videoSrc" 
            class="cover-video" 
            muted 
            preload="metadata"
          ></video>
          <div class="mask"></div>
        </div>

      </div>

      <!-- 底部指示点 -->
      <div class="dots">
        <span 
          v-for="(item, index) in mediaList" 
          :key="index" 
          :class="{ active: currentIndex === index }"
          @click="switchToIndex(index)"
        ></span>
      </div>
    </div>

    <!-- 搜索栏 (保持不变) -->
    <div class="search-section">
      <div class="search-bar">
        <input type="text" placeholder="请输入检索词......" />
        <button class="ai-search-btn">AI检索</button>
      </div>
    </div>

    <!-- 底部资源卡片 (保持不变) -->
    <div class="resource-grid">
      <div class="resource-item" v-for="item in resourceList" :key="item.id">
        <div class="res-img-container">
          <img :src="item.imgUrl" class="res-img" />
        </div>
        <div class="res-info">
          <h3>{{ item.title }}</h3>
          <span class="res-type">{{ item.type }}</span>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, computed } from 'vue';

// --- 1. 数据准备 ---
// 改动：删除了 cover 字段，只保留 videoSrc
const mediaList = [
  { 
    id: 1, 
    videoSrc: '/videos/v1.mp4'
  },
  { 
    id: 2, 
    videoSrc: '/videos/v2.mp4'
  },
  { 
    id: 3, 
    videoSrc: '/videos/v3.mp4'
  }
];

const currentIndex = ref(0);

// --- 2. 计算属性 ---
const currentItem = computed(() => mediaList[currentIndex.value]);

const prevItem = computed(() => {
  const prevIndex = (currentIndex.value - 1 + mediaList.length) % mediaList.length;
  return mediaList[prevIndex];
});

const nextItem = computed(() => {
  const nextIndex = (currentIndex.value + 1) % mediaList.length;
  return mediaList[nextIndex];
});

// --- 3. 切换逻辑 ---
const nextSlide = () => {
  currentIndex.value = (currentIndex.value + 1) % mediaList.length;
};

const prevSlide = () => {
  currentIndex.value = (currentIndex.value - 1 + mediaList.length) % mediaList.length;
};

const switchToIndex = (index) => {
  currentIndex.value = index;
};

const handleVideoEnd = () => {
  nextSlide();
};

// 底部卡片数据
const resourceList = ref([
  { id: 1, title: '中秋节', type: '传统节日', imgUrl: '/images/1.jpg' },
  { id: 2, title: '清明节', type: '传统节日', imgUrl: '/images/2.jpg' },
  { id: 3, title: '舞龙', type: '民俗活动', imgUrl: '/images/3.jpg' },
  { id: 4, title: '粽子', type: '节令食品', imgUrl: '/images/4.jpg' }
]);
</script>

<style scoped>
.home-container {
  max-width: 1300px;
  margin: 0 auto;
  padding: 20px;
}

/* 轮播区域 */
.carousel-section {
  position: relative;
  height: 400px;
  margin-bottom: 40px;
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
  width: 60%; 
  height: 360px;
  z-index: 10;
  transform: scale(1);
}

.video-box { width: 100%; height: 100%; }
.video-box video { width: 100%; height: 100%; object-fit: contain; }

/* 两侧卡片 */
.card.side {
  width: 20%;
  height: 280px;
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
.dots span { width: 8px; height: 8px; border-radius: 50%; background: #ccc; cursor: pointer; }
.dots span.active { background: #409eff; width: 24px; border-radius: 4px; }

/* 搜索栏 & 底部卡片 (保持不变) */
.search-section { display: flex; justify-content: center; margin: 50px 0; }
.search-bar { display: flex; width: 60%; border: 1px solid #eee; border-radius: 4px; overflow: hidden; }
.search-bar input { flex: 1; border: none; padding: 15px 20px; outline: none; background: white; }
.ai-search-btn { background-color: #409eff; color: white; border: none; padding: 0 30px; cursor: pointer; }

.resource-grid { display: flex; gap: 20px; }
.resource-item { 
  flex: 1; background: white; border-radius: 8px; overflow: hidden; 
  box-shadow: 0 2px 8px rgba(0,0,0,0.05); border: 1px solid #f0f0f0;
  cursor: pointer; transition: all 0.3s ease; 
}
.resource-item:hover { transform: translateY(-5px); box-shadow: 0 12px 24px rgba(0,0,0,0.12); border-color: #ecf5ff; }
.res-img-container { height: 160px; overflow: hidden; }
.res-img { width: 100%; height: 100%; object-fit: cover; transition: transform 0.5s ease; }
.resource-item:hover .res-img { transform: scale(1.08); }
.res-info { padding: 15px; }
.res-info h3 { margin: 0 0 5px; font-size: 16px; color: #333; transition: color 0.3s; }
.resource-item:hover h3 { color: #409eff; }
.res-type { font-size: 12px; color: #409eff; background: #ecf5ff; padding: 2px 6px; border-radius: 4px; }
</style>