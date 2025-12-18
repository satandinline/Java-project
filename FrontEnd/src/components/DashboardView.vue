<template>
  <div class="dashboard-container">
    <!-- 当前日期和时间 -->
    <div class="datetime-display">
      <div class="current-date">{{ currentDate }}</div>
      <div class="current-time">{{ currentTime }}</div>
    </div>

    <div class="dashboard-header">
      <h1>数据大屏</h1>
      <button class="refresh-btn" @click="loadStatistics">🔄 刷新</button>
    </div>

    <!-- 加载状态 -->
    <div v-if="isLoading" class="loading-section">
      <p>正在加载统计数据...</p>
    </div>

    <!-- 错误提示 -->
    <div v-if="error" class="error-section">
      <p class="error-message">{{ error }}</p>
      <button class="retry-btn" @click="loadStatistics">重试</button>
    </div>

    <!-- 数据大屏内容 -->
    <div v-if="!isLoading && !error && statistics" class="dashboard-content">
      <!-- 核心指标卡片 -->
      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-icon">👥</div>
          <div class="stat-content">
            <div class="stat-label">历史访问人次</div>
            <div class="stat-value">{{ statistics.total_users || 0 }}</div>
          </div>
        </div>

        <div class="stat-card">
          <div class="stat-icon">📅</div>
          <div class="stat-content">
            <div class="stat-label">今日访问人次</div>
            <div class="stat-value highlight">{{ statistics.today_users || 0 }}</div>
          </div>
        </div>

        <div class="stat-card">
          <div class="stat-icon">💬</div>
          <div class="stat-content">
            <div class="stat-label">历史文字AIGC使用人次</div>
            <div class="stat-value">{{ statistics.total_text_users || 0 }}</div>
            <div class="stat-sub">总次数: {{ statistics.total_text_count || 0 }}</div>
          </div>
        </div>

        <div class="stat-card">
          <div class="stat-icon">📅💬</div>
          <div class="stat-content">
            <div class="stat-label">今日文字AIGC使用人次</div>
            <div class="stat-value highlight">{{ statistics.today_text_users || 0 }}</div>
            <div class="stat-sub">今日次数: {{ statistics.today_text_count || 0 }}</div>
          </div>
        </div>

        <div class="stat-card">
          <div class="stat-icon">🖼️</div>
          <div class="stat-content">
            <div class="stat-label">历史图片AIGC使用人次</div>
            <div class="stat-value">{{ statistics.total_image_users || 0 }}</div>
            <div class="stat-sub">总次数: {{ statistics.total_image_count || 0 }}</div>
          </div>
        </div>

        <div class="stat-card">
          <div class="stat-icon">📅🖼️</div>
          <div class="stat-content">
            <div class="stat-label">今日图片AIGC使用人次</div>
            <div class="stat-value highlight">{{ statistics.today_image_users || 0 }}</div>
            <div class="stat-sub">今日次数: {{ statistics.today_image_count || 0 }}</div>
          </div>
        </div>
      </div>

      <!-- 趋势图表 -->
      <div class="chart-section">
        <h2>最近7天使用趋势</h2>
        <div class="chart-container">
          <canvas ref="trendChart" id="trendChart"></canvas>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue';
import { useRouter } from 'vue-router';

const router = useRouter();

const statistics = ref(null);
const isLoading = ref(false);
const error = ref(null);
const trendChart = ref(null);
const currentDate = ref('');
const currentTime = ref('');

// 更新当前日期和时间
const updateDateTime = () => {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  const hours = String(now.getHours()).padStart(2, '0');
  const minutes = String(now.getMinutes()).padStart(2, '0');
  const seconds = String(now.getSeconds()).padStart(2, '0');
  
  currentDate.value = `${year}年${month}月${day}日`;
  currentTime.value = `${hours}:${minutes}:${seconds}`;
};

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

// 加载统计数据
const loadStatistics = async () => {
  isLoading.value = true;
  error.value = null;

  try {
    const userInfo = getCurrentUser();
    if (!userInfo || !userInfo.id) {
      error.value = '请先登录';
      return;
    }

    // 注意：前端只做基本检查，真正的权限验证在API后端（从数据库users表读取role字段）
    // 如果前端role字段不存在或不正确，后端会返回403错误

    const response = await fetch(`/api/admin/dashboard/statistics?user_id=${userInfo.id}`);
    const data = await response.json();

    if (data.success) {
      statistics.value = data.data;
      // 等待DOM更新后绘制图表
      await nextTick();
      drawTrendChart();
    } else {
      error.value = data.message || '获取统计数据失败';
    }
  } catch (err) {
    console.error('获取统计数据失败:', err);
    error.value = `加载失败：${err.message || '未知错误'}`;
  } finally {
    isLoading.value = false;
  }
};

// 绘制趋势图表
const drawTrendChart = () => {
  if (!statistics.value || !statistics.value.trend_data || !trendChart.value) {
    return;
  }

  const canvas = trendChart.value;
  const ctx = canvas.getContext('2d');
  const trendData = statistics.value.trend_data;

  // 设置画布尺寸
  const container = canvas.parentElement;
  canvas.width = container.clientWidth;
  canvas.height = 300;

  // 清空画布
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  if (trendData.length === 0) {
    ctx.fillStyle = '#999';
    ctx.font = '16px Arial';
    ctx.textAlign = 'center';
    ctx.fillText('暂无数据', canvas.width / 2, canvas.height / 2);
    return;
  }

  // 计算最大值（用于缩放）
  const maxUsers = Math.max(...trendData.map(d => d.daily_users || 0), 1);
  const maxCount = Math.max(
    ...trendData.map(d => (d.text_count || 0) + (d.image_count || 0)),
    1
  );

  const padding = 40;
  const chartWidth = canvas.width - padding * 2;
  const chartHeight = canvas.height - padding * 2;
  const barWidth = chartWidth / trendData.length * 0.6;
  const spacing = chartWidth / trendData.length * 0.4;

  // 绘制坐标轴
  ctx.strokeStyle = '#ddd';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(padding, padding);
  ctx.lineTo(padding, canvas.height - padding);
  ctx.lineTo(canvas.width - padding, canvas.height - padding);
  ctx.stroke();

  // 绘制数据
  trendData.forEach((item, index) => {
    const x = padding + index * (barWidth + spacing) + spacing / 2;
    const date = new Date(item.date);
    const dateStr = `${date.getMonth() + 1}/${date.getDate()}`;

    // 绘制使用人次柱状图
    const usersHeight = (item.daily_users || 0) / maxUsers * chartHeight;
    ctx.fillStyle = '#409eff';
    ctx.fillRect(x, canvas.height - padding - usersHeight, barWidth, usersHeight);

    // 绘制文字AIGC次数
    const textHeight = (item.text_count || 0) / maxCount * chartHeight * 0.5;
    ctx.fillStyle = '#67c23a';
    ctx.fillRect(x, canvas.height - padding - usersHeight - textHeight, barWidth * 0.4, textHeight);

    // 绘制图片AIGC次数
    const imageHeight = (item.image_count || 0) / maxCount * chartHeight * 0.5;
    ctx.fillStyle = '#e6a23c';
    ctx.fillRect(x + barWidth * 0.4, canvas.height - padding - usersHeight - imageHeight, barWidth * 0.4, imageHeight);

    // 绘制日期标签
    ctx.fillStyle = '#666';
    ctx.font = '12px Arial';
    ctx.textAlign = 'center';
    ctx.fillText(dateStr, x + barWidth / 2, canvas.height - padding + 20);
  });

  // 绘制图例
  const legendY = 20;
  const legendItems = [
    { color: '#409eff', label: '使用人次' },
    { color: '#67c23a', label: '文字AIGC' },
    { color: '#e6a23c', label: '图片AIGC' }
  ];

  legendItems.forEach((item, index) => {
    const x = padding + index * 100;
    ctx.fillStyle = item.color;
    ctx.fillRect(x, legendY, 15, 15);
    ctx.fillStyle = '#333';
    ctx.font = '12px Arial';
    ctx.textAlign = 'left';
    ctx.fillText(item.label, x + 20, legendY + 12);
  });
};

onMounted(() => {
  updateDateTime();
  // 每秒更新一次时间
  setInterval(updateDateTime, 1000);
  
  loadStatistics();
  // 每30秒自动刷新统计数据
  setInterval(loadStatistics, 30000);
});
</script>

<style scoped>
.dashboard-container {
  padding: 20px;
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.datetime-display {
  text-align: center;
  color: white;
  margin-bottom: 20px;
  padding: 15px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 10px;
  backdrop-filter: blur(10px);
}

.current-date {
  font-size: 24px;
  font-weight: bold;
  margin-bottom: 8px;
}

.current-time {
  font-size: 36px;
  font-weight: bold;
  font-family: 'Courier New', monospace;
  letter-spacing: 2px;
}

.dashboard-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 30px;
  color: white;
}

.dashboard-header h1 {
  margin: 0;
  font-size: 32px;
  font-weight: bold;
}

.refresh-btn {
  padding: 10px 20px;
  background: rgba(255, 255, 255, 0.2);
  color: white;
  border: 1px solid rgba(255, 255, 255, 0.3);
  border-radius: 5px;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.3s;
}

.refresh-btn:hover {
  background: rgba(255, 255, 255, 0.3);
}

.loading-section,
.error-section {
  text-align: center;
  padding: 40px;
  color: white;
}

.error-message {
  margin-bottom: 20px;
}

.retry-btn {
  padding: 10px 20px;
  background: rgba(255, 255, 255, 0.2);
  color: white;
  border: 1px solid rgba(255, 255, 255, 0.3);
  border-radius: 5px;
  cursor: pointer;
}

.dashboard-content {
  animation: fadeIn 0.5s;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 20px;
  margin-bottom: 30px;
}

.stat-card {
  background: rgba(255, 255, 255, 0.95);
  border-radius: 10px;
  padding: 20px;
  display: flex;
  align-items: center;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  transition: transform 0.3s;
}

.stat-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 6px 12px rgba(0, 0, 0, 0.15);
}

.stat-icon {
  font-size: 48px;
  margin-right: 20px;
}

.stat-content {
  flex: 1;
}

.stat-label {
  font-size: 14px;
  color: #666;
  margin-bottom: 8px;
}

.stat-value {
  font-size: 32px;
  font-weight: bold;
  color: #333;
}

.stat-value.highlight {
  color: #409eff;
}

.stat-sub {
  font-size: 12px;
  color: #999;
  margin-top: 4px;
}

.chart-section {
  background: rgba(255, 255, 255, 0.95);
  border-radius: 10px;
  padding: 20px;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

.chart-section h2 {
  margin: 0 0 20px 0;
  color: #333;
  font-size: 20px;
}

.chart-container {
  width: 100%;
  height: 300px;
}

#trendChart {
  width: 100%;
  height: 100%;
}
</style>

