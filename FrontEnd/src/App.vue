<template>
  <div class="app">
    <header class="top-bar">
      <div class="logo-area">logo + 系统名称</div>

      <div class="filters">
        <select>
          <option>节日名称</option>
        </select>
        <select>
          <option>你好</option>
        </select>
        <select>
          <option>hello</option>
        </select>
        <select>
          <option>节日名称</option>
        </select>
        <select>
          <option>你好</option>
        </select>
      </div>

      <div class="user-actions">
        <button class="btn secondary">用户上传</button>
        <button class="btn primary">登录/注册</button>
      </div>
    </header>

    <main class="page">
      <section class="banner-section">
        <div class="banner-wrapper">
          <div
            class="banner-track"
            :style="{ transform: `translateX(-${currentBanner * 100}%)` }"
          >
            <div
              class="banner-slide"
              v-for="banner in banners"
              :key="banner.id"
            >
              
              <div class="banner-item"></div>
              <div class="banner-item"></div>
              <div class="banner-item"></div>
            </div>
          </div>

          
          <button class="banner-arrow left" @click="prevBanner">‹</button>
          <button class="banner-arrow right" @click="nextBanner">›</button>
        </div>


        <div class="banner-dots">
          <span
            v-for="(banner, index) in banners"
            :key="banner.id"
            class="dot"
            :class="{ active: index === currentBanner }"
            @click="goBanner(index)"
          ></span>
        </div>
      </section>

      <section class="search-section">
        <input class="search-input" placeholder="请输入检索词……" />
        <button class="btn primary search-btn">AI检索</button>
      </section>

      <section class="card-section">
        <div class="card" v-for="i in 4" :key="i">
          <div class="card-image"></div>
          <div class="card-body">
            <div class="card-title">文化实体名称</div>
            <div class="card-meta">类型</div>
            <div class="card-desc">简介简介简介简介简介</div>
          </div>
        </div>
      </section>
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'

const banners = ref([
  { id: 1 },
  { id: 2 },
  { id: 3 }
])

const currentBanner = ref(0)
let timerId = null

const goBanner = (index) => {
  currentBanner.value = index
}

const nextBanner = () => {
  currentBanner.value = (currentBanner.value + 1) % banners.value.length
}

const prevBanner = () => {
  currentBanner.value =
    (currentBanner.value - 1 + banners.value.length) % banners.value.length
}

const startAutoPlay = () => {
  if (timerId) return
  timerId = setInterval(() => {
    nextBanner()
  }, 3000) // 每 3000ms 切换一页
}

const stopAutoPlay = () => {
  if (timerId) {
    clearInterval(timerId)
    timerId = null
  }
}


onMounted(() => {
  startAutoPlay()
})

onBeforeUnmount(() => {
  stopAutoPlay()
})
</script>


<style scoped>
* {
  box-sizing: border-box;
}

.app {
  min-height: 100vh;
  background-color: #f5f5f5;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui,
    sans-serif;
  color: #333;
}

.top-bar {
  height: 64px;
  padding: 0 32px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background-color: #ffffff;
  border-bottom: 1px solid #e5e5e5;
}

.logo-area {
  font-weight: 600;
  font-size: 16px;
  white-space: nowrap;
  margin-right: 24px;
  flex-shrink: 0;
}

.filters {
  display: flex;
  gap: 12px;
  flex: 1;
  justify-content: flex-start;
}

.filters select {
  padding: 6px 10px;
  border-radius: 4px;
  border: 1px solid #dcdcdc;
  background-color: #ffffff;
  font-size: 14px;
}

.user-actions {
  display: flex;
  gap: 12px;
  flex-shrink: 0;
}

.btn {
  padding: 6px 14px;
  border-radius: 18px;
  border: 1px solid transparent;
  font-size: 14px;
  cursor: pointer;
  white-space: nowrap;
}

.btn.primary {
  background-color: #409eff;
  color: #ffffff;
  border-color: #409eff;
}

.btn.secondary {
  background-color: #ffffff;
  color: #333;
  border-color: #dcdcdc;
}


.page {
  max-width: 1200px;
  margin: 24px auto 40px;
  padding: 0 16px;
}


.banner-section {
  margin-bottom: 24px;
}


.banner-wrapper {
  position: relative;
  overflow: hidden;
  border-radius: 8px;
}


.banner-track {
  display: flex;
  transition: transform 0.4s ease;
}


.banner-slide {
  flex: 0 0 100%;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  padding: 16px;
  background-color: #f5f5f5;
}

.banner-item {
  height: 220px;
  background-color: #e9e9e9;
  border-radius: 8px;
}


.banner-arrow {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: none;
  background-color: rgba(255, 255, 255, 0.9);
  box-shadow: 0 0 4px rgba(0, 0, 0, 0.1);
  cursor: pointer;
  font-size: 20px;
  line-height: 32px;
  text-align: center;
}

.banner-arrow.left {
  left: 8px;
}

.banner-arrow.right {
  right: 8px;
}


.banner-dots {
  display: flex;
  justify-content: center;
  margin-top: 8px;
  gap: 8px;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: #d0d0d0;
  cursor: pointer;
}

.dot.active {
  background-color: #409eff;
}

/* 搜索区 */
.search-section {
  margin: 32px auto 24px;
  max-width: 700px;
  display: flex;
}

.search-input {
  flex: 1;
  padding: 10px 12px;
  border-radius: 24px 0 0 24px;
  border: 1px solid #dcdcdc;
  border-right: none;
  font-size: 14px;
  outline: none;
}

.search-btn {
  border-radius: 0 24px 24px 0;
}

/* 卡片区 */
.card-section {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.card {
  background-color: #ffffff;
  border-radius: 6px;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
  display: flex;
  flex-direction: column;
}

.card-image {
  height: 140px;
  background-color: #e9e9e9;
}

.card-body {
  padding: 10px 12px 14px;
}

.card-title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 4px;
}

.card-meta {
  font-size: 12px;
  color: #888;
  margin-bottom: 6px;
}

.card-desc {
  font-size: 12px;
  color: #4f4545;
}


@media (max-width: 900px) {
  .card-section {
    grid-template-columns: repeat(2, 1fr);
  }

  .banner-slide {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 600px) {
  .card-section {
    grid-template-columns: 1fr;
  }

  .filters {
    display: none;
  }
}
</style>
