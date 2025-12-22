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
        <!-- 访问数据组 -->
        <div class="stat-card stat-card-primary">
          <div class="stat-icon">👥</div>
          <div class="stat-content">
            <div class="stat-label">历史访问人次</div>
            <div class="stat-value">{{ statistics.total_users || 0 }}</div>
          </div>
        </div>

        <div class="stat-card stat-card-primary">
          <div class="stat-icon">📅</div>
          <div class="stat-content">
            <div class="stat-label">今日访问人次</div>
            <div class="stat-value highlight">{{ statistics.today_users || 0 }}</div>
          </div>
        </div>

        <!-- 文字AIGC组 -->
        <div class="stat-card stat-card-secondary">
          <div class="stat-icon">💬</div>
          <div class="stat-content">
            <div class="stat-label">历史文字AIGC使用人次</div>
            <div class="stat-value">{{ statistics.total_text_users || 0 }}</div>
            <div class="stat-sub">总次数: {{ statistics.total_text_count || 0 }}</div>
          </div>
        </div>

        <div class="stat-card stat-card-secondary">
          <div class="stat-icon">📅💬</div>
          <div class="stat-content">
            <div class="stat-label">今日文字AIGC使用人次</div>
            <div class="stat-value highlight">{{ statistics.today_text_users || 0 }}</div>
            <div class="stat-sub">今日次数: {{ statistics.today_text_count || 0 }}</div>
          </div>
        </div>

        <!-- 图片AIGC组 -->
        <div class="stat-card stat-card-tertiary">
          <div class="stat-icon">🖼️</div>
          <div class="stat-content">
            <div class="stat-label">历史图片AIGC使用人次</div>
            <div class="stat-value">{{ statistics.total_image_users || 0 }}</div>
            <div class="stat-sub">总次数: {{ statistics.total_image_count || 0 }}</div>
          </div>
        </div>

        <div class="stat-card stat-card-tertiary">
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
        <div class="charts-grid">
          <!-- 访问人次趋势图 -->
          <div class="chart-item">
            <h3>访问人次趋势</h3>
            <div class="chart-container">
              <canvas ref="usersChart" id="usersChart"></canvas>
            </div>
          </div>
          
          <!-- 文字AIGC使用人次趋势图 -->
          <div class="chart-item">
            <h3>文字AIGC使用人次趋势</h3>
            <div class="chart-container">
              <canvas ref="textChart" id="textChart"></canvas>
            </div>
          </div>
          
          <!-- 图片AIGC使用人次趋势图 -->
          <div class="chart-item">
            <h3>图片AIGC使用人次趋势</h3>
            <div class="chart-container">
              <canvas ref="imageChart" id="imageChart"></canvas>
            </div>
          </div>
          
          <!-- AIGC总使用人次趋势图 -->
          <div class="chart-item">
            <h3>AIGC总使用人次趋势</h3>
            <div class="chart-container">
              <canvas ref="totalAigcChart" id="totalAigcChart"></canvas>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, watch } from 'vue';
import { useRouter } from 'vue-router';

const router = useRouter();

const statistics = ref(null);
const isLoading = ref(false);
const error = ref(null);
const usersChart = ref(null);
const textChart = ref(null);
const imageChart = ref(null);
const totalAigcChart = ref(null);
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

    const response = await fetch(`/api/statistics?userId=${userInfo.id}`);
    
    if (!response.ok) {
      if (response.status === 403) {
        const errorData = await response.json().catch(() => ({}));
        error.value = errorData.message || '权限不足,仅管理员可访问';
      } else {
        error.value = `加载失败：HTTP ${response.status}`;
      }
      return;
    }
    
    const data = await response.json();
    
    if (data.success) {
      statistics.value = data.data;
      console.log('统计数据加载成功:', statistics.value);
      // 等待DOM更新后绘制图表（通过watch自动触发）
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

// 绘制所有趋势图表（带重试机制）
const drawAllCharts = (retryCount = 0, maxRetries = 5) => {
  if (!statistics.value || !statistics.value.trend_data) {
    console.log('图表绘制条件不满足:', {
      hasStatistics: !!statistics.value,
      hasTrendData: !!(statistics.value && statistics.value.trend_data)
    });
    return;
  }

  // 检查所有canvas ref是否存在
  const missingCanvas = [];
  if (!usersChart.value) missingCanvas.push('usersChart');
  if (!textChart.value) missingCanvas.push('textChart');
  if (!imageChart.value) missingCanvas.push('imageChart');
  if (!totalAigcChart.value) missingCanvas.push('totalAigcChart');
  
  if (missingCanvas.length > 0) {
    if (retryCount < maxRetries) {
      const delay = Math.min(200 * (retryCount + 1), 1000); // 递增延迟，最多1秒
      console.warn(`部分canvas未找到，跳过绘制: ${missingCanvas.join(', ')} (重试 ${retryCount + 1}/${maxRetries})`);
      setTimeout(() => {
        drawAllCharts(retryCount + 1, maxRetries);
      }, delay);
      return;
    } else {
      console.error('Canvas元素始终未找到，请检查DOM结构:', missingCanvas);
      return;
    }
  }

  let trendData = statistics.value.trend_data || [];

  // 直接使用后端返回的数据（后端已经确保有7天数据，且最后一天是今天）
  // 后端返回的数据已经按i从6到0的顺序，即从6天前到今天
  // 但为了确保顺序正确，我们按日期排序
  trendData.sort((a, b) => {
    if (!a || !a.date || !b || !b.date) return 0;
    // 直接比较日期字符串（YYYY-MM-DD格式）
    return a.date.localeCompare(b.date);
  });
  
  // 调试输出
  console.log('趋势数据（后端返回，排序后）:', trendData.map(d => ({ 
    date: d.date, 
    daily_users: d.daily_users, 
    text_count: d.text_count,
    image_count: d.image_count
  })));
  
  // 验证数据完整性：确保有7条数据
  const requiredDays = 7;
  if (trendData.length !== requiredDays) {
    console.warn(`趋势数据条数不正确：期望${requiredDays}条，实际${trendData.length}条`);
  }
  
  // 验证最后一天是否是今天（使用后端返回的日期作为标准，因为后端使用数据库CURDATE()更准确）
  // 注意：前端计算的日期可能有时区问题，所以信任后端返回的日期
  if (trendData.length > 0) {
    const lastDate = trendData[trendData.length - 1].date;
    // 后端返回的最后一天应该是数据库的今天（CURDATE()），这是准确的
    // 不再进行前端日期比较，避免时区问题
    console.log(`趋势数据最后一天：${lastDate}（由数据库CURDATE()确定）`);
  }

  // 绘制四个独立的图表
  drawSingleChart(usersChart.value, trendData, 'daily_users', '#409eff', '访问人次');
  drawSingleChart(textChart.value, trendData, 'text_count', '#67c23a', '文字AIGC使用人次');
  drawSingleChart(imageChart.value, trendData, 'image_count', '#e6a23c', '图片AIGC使用人次');
  drawSingleChart(totalAigcChart.value, trendData, 'total_aigc_count', '#f56c6c', 'AIGC总使用人次');
};

// 绘制单个趋势图表
const drawSingleChart = (canvas, trendData, dataKey, color, label) => {
  if (!canvas) {
    console.error(`无法找到画布: ${label}`);
    return;
  }

  const ctx = canvas.getContext('2d');
  
  // 设置画布尺寸
  const container = canvas.parentElement;
  if (!container) {
    console.error('无法找到画布容器');
    return;
  }
  canvas.width = container.clientWidth || 800;
  canvas.height = 300;

  // 清空画布
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  // 如果数据为空，显示提示
  if (!trendData || trendData.length === 0) {
    ctx.fillStyle = '#999';
    ctx.font = '16px Arial';
    ctx.textAlign = 'center';
    ctx.fillText('暂无数据', canvas.width / 2, canvas.height / 2);
    return;
  }

  // 计算最大值（用于缩放）
  const actualMaxValue = Math.max(...trendData.map(d => d[dataKey] || 0));
  // 当所有数据都是0时，使用固定的最大值6，否则使用实际最大值（至少为1）
  const maxValue = actualMaxValue === 0 ? 6 : Math.max(actualMaxValue, 1);

  const padding = { top: 40, right: 40, bottom: 50, left: 50 };
  const chartWidth = canvas.width - padding.left - padding.right;
  const chartHeight = canvas.height - padding.top - padding.bottom;

  // 绘制坐标轴
  ctx.strokeStyle = '#ddd';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(padding.left, padding.top);
  ctx.lineTo(padding.left, canvas.height - padding.bottom);
  ctx.lineTo(canvas.width - padding.right, canvas.height - padding.bottom);
  ctx.stroke();

  // 计算X坐标点位置
  const getX = (index) => {
    if (trendData.length === 1) {
      return padding.left + chartWidth / 2;
    }
    return padding.left + (index / (trendData.length - 1)) * chartWidth;
  };

  // 计算Y坐标点位置
  const getY = (value) => {
    const ratio = value / maxValue;
    return canvas.height - padding.bottom - (ratio * chartHeight);
  };

  // 绘制折线
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.beginPath();
  trendData.forEach((item, index) => {
    const x = getX(index);
    const y = getY(item[dataKey] || 0);
    if (index === 0) {
      ctx.moveTo(x, y);
    } else {
      ctx.lineTo(x, y);
    }
  });
  ctx.stroke();

  // 绘制数据点
  ctx.fillStyle = color;
  trendData.forEach((item, index) => {
    const x = getX(index);
    const y = getY(item[dataKey] || 0);
    ctx.beginPath();
    ctx.arc(x, y, 4, 0, Math.PI * 2);
    ctx.fill();
  });

  // 绘制日期标签
  ctx.fillStyle = '#666';
  ctx.font = '12px Arial';
  ctx.textAlign = 'center';
  trendData.forEach((item, index) => {
    const x = getX(index);
    let dateStr = '';
    
    if (item.date) {
      const date = new Date(item.date + 'T00:00:00');
      if (!isNaN(date.getTime())) {
        dateStr = `${date.getMonth() + 1}/${date.getDate()}`;
      } else {
        dateStr = item.date.substring(5).replace('-', '/');
      }
    }
    
    ctx.fillText(dateStr, x, canvas.height - padding.bottom + 20);
  });

  // 绘制Y轴刻度
  ctx.fillStyle = '#666';
  ctx.font = '10px Arial';
  ctx.textAlign = 'right';
  // 当所有数据都是0时，显示0、1、2、3、4、5、6
  if (actualMaxValue === 0) {
    for (let i = 0; i <= 6; i++) {
      const y = canvas.height - padding.bottom - (i / 6) * chartHeight;
      ctx.fillText(i.toString(), padding.left - 10, y + 4);
    }
  } else {
    // 有数据时，显示5个刻度点
    for (let i = 0; i <= 5; i++) {
      const value = Math.round((maxValue / 5) * i);
      const y = canvas.height - padding.bottom - (i / 5) * chartHeight;
      ctx.fillText(value.toString(), padding.left - 10, y + 4);
    }
  }

  // 绘制图例
  const legendY = 15;
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.moveTo(padding.left, legendY);
  ctx.lineTo(padding.left + 20, legendY);
  ctx.stroke();
  ctx.beginPath();
  ctx.arc(padding.left + 10, legendY, 3, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = '#333';
  ctx.font = '12px Arial';
  ctx.textAlign = 'left';
  ctx.fillText(label, padding.left + 25, legendY + 4);
};

// 监听statistics变化，当数据加载完成后自动绘制图表
watch(statistics, (newValue) => {
  if (newValue && newValue.trend_data) {
    // 等待DOM更新后绘制图表
    nextTick(() => {
      requestAnimationFrame(() => {
        nextTick(() => {
          // 延迟一小段时间确保所有canvas元素都已渲染
          setTimeout(() => {
            drawAllCharts();
          }, 100);
        });
      });
    });
  }
}, { immediate: false });

onMounted(async () => {
  updateDateTime();
  // 每秒更新一次时间
  setInterval(updateDateTime, 1000);
  
  // 等待DOM完全渲染后再加载统计数据
  await nextTick();
  // 使用requestAnimationFrame确保所有元素都已渲染
  requestAnimationFrame(async () => {
    await nextTick();
    // 再次延迟确保canvas元素已渲染
    setTimeout(async () => {
      await loadStatistics();
      // 每30秒自动刷新统计数据
      setInterval(loadStatistics, 30000);
    }, 100);
  });
});
</script>

<style scoped>
.dashboard-container {
  padding: 30px;
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  max-width: 1600px;
  margin: 0 auto;
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
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
  margin-bottom: 30px;
}

/* 响应式布局 */
@media (max-width: 1200px) {
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }
}

.stat-card {
  background: rgba(255, 255, 255, 0.95);
  border-radius: 12px;
  padding: 24px;
  display: flex;
  align-items: center;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  transition: all 0.3s ease;
  min-height: 120px;
  border: 1px solid rgba(255, 255, 255, 0.3);
}

.stat-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 8px 16px rgba(0, 0, 0, 0.2);
  border-color: rgba(255, 255, 255, 0.5);
}

/* 卡片分组样式 */
.stat-card-primary {
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%);
  border-left: 4px solid #667eea;
}

.stat-card-secondary {
  background: linear-gradient(135deg, rgba(103, 194, 58, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%);
  border-left: 4px solid #67c23a;
}

.stat-card-tertiary {
  background: linear-gradient(135deg, rgba(230, 162, 60, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%);
  border-left: 4px solid #e6a23c;
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
  border-radius: 12px;
  padding: 30px;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  margin-top: 20px;
}

.chart-section h2 {
  margin: 0 0 25px 0;
  color: #333;
  font-size: 24px;
  font-weight: 600;
  border-bottom: 2px solid #e0e0e0;
  padding-bottom: 15px;
}

.charts-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
  margin-top: 20px;
}

/* 响应式布局 */
@media (max-width: 1200px) {
  .charts-grid {
    grid-template-columns: 1fr;
  }
}

.chart-item {
  background: rgba(255, 255, 255, 0.5);
  border-radius: 8px;
  padding: 15px;
  border: 1px solid #e0e0e0;
}

.chart-item h3 {
  margin: 0 0 15px 0;
  color: #333;
  font-size: 16px;
  font-weight: 600;
  text-align: center;
}

.chart-container {
  width: 100%;
  height: 300px;
  position: relative;
  background: rgba(255, 255, 255, 0.8);
  border-radius: 8px;
  padding: 10px;
}

.chart-container canvas {
  width: 100%;
  height: 100%;
  display: block;
}
</style>

