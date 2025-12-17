<template>
  <div class="annotation-container">
    <h2>标注任务管理</h2>
    
    <div class="filter-bar">
      <select v-model="statusFilter" @change="fetchTasks">
        <option value="">所有状态</option>
        <option value="待标注">待标注</option>
        <option value="已标注">已标注</option>
      </select>
    </div>
    
    <div class="tasks-list">
      <div class="task-card" v-for="task in tasks" :key="task.id">
        <div class="task-header">
          <h3>{{ task.title }}</h3>
          <span class="task-status" :class="task.status">{{ task.status }}</span>
        </div>
        
        <div class="task-info">
          <p>资源类型: {{ task.resource_type }}</p>
          <p>任务类型: {{ task.task_type }}</p>
          <p>标注方式: {{ task.annotation_method === 'ai' ? 'AI标注' : '人工标注' }}</p>
        </div>
        
        <div class="task-actions">
          <button @click="viewAnnotation(task.id)">查看标注</button>
          <button 
            @click="editAnnotation(task.id)" 
            v-if="task.status === '已标注'"
          >
            编辑标注
          </button>
          <button 
            @click="approveAnnotation(task.id)" 
            v-if="task.status === '已标注' && isAdmin"
            class="approve-btn"
          >
            审核通过
          </button>
          <button 
            @click="rejectAnnotation(task.id)" 
            v-if="task.status === '已标注' && isAdmin"
            class="reject-btn"
          >
            驳回
          </button>
        </div>
      </div>
    </div>
    
    <!-- 标注编辑弹窗 -->
    <div class="modal" v-if="showAnnotationModal">
      <div class="modal-content">
        <span class="close-btn" @click="closeAnnotationModal">&times;</span>
        <h3>标注编辑</h3>
        
        <div class="annotation-content">
          <div v-if="currentAnnotation">
            <h4>实体标注信息:</h4>
            
            <div class="form-group">
              <label>实体名称 *</label>
              <input 
                type="text" 
                v-model="currentAnnotation.entity_name" 
                placeholder="请输入实体名称"
                required
              >
            </div>
            
            <div class="form-group">
              <label>实体类型 *</label>
              <select v-model="currentAnnotation.entity_type">
                <option value="人物">人物</option>
                <option value="作品">作品</option>
                <option value="事件">事件</option>
                <option value="地点">地点</option>
                <option value="其他">其他</option>
              </select>
            </div>
            
            <div class="form-group">
              <label>描述</label>
              <textarea 
                v-model="currentAnnotation.description"
                placeholder="请输入实体描述..."
                rows="3"
              ></textarea>
            </div>
            
            <div class="form-group">
              <label>来源</label>
              <input 
                type="text" 
                v-model="currentAnnotation.source" 
                placeholder="请输入来源信息"
              >
            </div>
            
            <div class="form-row">
              <div class="form-group">
                <label>时期年代</label>
                <input 
                  type="text" 
                  v-model="currentAnnotation.period_era" 
                  placeholder="例如：唐代、明清"
                >
              </div>
              
              <div class="form-group">
                <label>地理坐标</label>
                <input 
                  type="text" 
                  v-model="currentAnnotation.geo_coordinates" 
                  placeholder="例如：经度,纬度"
                >
              </div>
            </div>
            
            <div class="form-group">
              <label>文化区域</label>
              <input 
                type="text" 
                v-model="currentAnnotation.cultural_region" 
                placeholder="例如：华北、江南"
              >
            </div>
            
            <div class="form-group">
              <label>风格特征</label>
              <textarea 
                v-model="currentAnnotation.style_features"
                placeholder="请输入风格特征..."
                rows="2"
              ></textarea>
            </div>
            
            <div class="form-group">
              <label>文化价值</label>
              <textarea 
                v-model="currentAnnotation.cultural_value"
                placeholder="请输入文化价值..."
                rows="2"
              ></textarea>
            </div>
            
            <div class="form-group">
              <label>相关图像链接</label>
              <input 
                type="text" 
                v-model="currentAnnotation.related_images_url" 
                placeholder="请输入图像URL"
              >
            </div>
            
            <div class="form-group">
              <label>数字资源链接</label>
              <input 
                type="text" 
                v-model="currentAnnotation.digital_resource_link" 
                placeholder="请输入数字资源URL"
              >
            </div>
            
            <div class="annotation-actions">
              <button class="save-annotation-btn" @click="saveAnnotation">保存标注</button>
              <button class="cancel-btn" @click="closeAnnotationModal">取消</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';

const tasks = ref([]);
const statusFilter = ref('');
const showAnnotationModal = ref(false);
const currentTaskId = ref(null);
// 检查是否为管理员
const isAdmin = ref(false);
const currentAnnotation = ref({
  // 新字段结构
  entity_name: '',
  entity_type: '其他',
  description: '',
  source: '',
  period_era: '',
  geo_coordinates: '',
  cultural_region: '',
  style_features: '',
  cultural_value: '',
  related_images_url: '',
  digital_resource_link: '',
  // 兼容旧格式
  entities: []
});

onMounted(() => {
  fetchTasks();
  // 检查用户角色
  const userInfo = JSON.parse(localStorage.getItem('userInfo'));
  isAdmin.value = userInfo && userInfo.role === '管理员';
});

const fetchTasks = async () => {
  const userInfo = JSON.parse(localStorage.getItem('userInfo'));
  if (!userInfo || !userInfo.id) {
    console.error("用户未登录");
    tasks.value = [];
    return;
  }
  
  try {
    const response = await fetch(`/api/annotation/tasks?user_id=${userInfo.id}${statusFilter.value ? `&status=${statusFilter.value}` : ''}`, {
      method: 'GET',
      headers: {
        'X-User-Id': userInfo.id.toString(),
        'Content-Type': 'application/json'
      }
    });
    
    const data = await response.json();
    
    if (data.success && data.tasks) {
      tasks.value = data.tasks.map(task => ({
        id: task.id,
        resource_id: task.resource_id,
        title: task.title || '未命名资源',
        resource_type: task.resource_type || '未知',
        task_type: task.task_type || '实体',
        status: task.status || '待标注',
        annotation_method: task.annotation_method || 'ai'
      }));
    } else {
      console.error("获取任务失败:", data.message || '未知错误');
      tasks.value = [];
    }
  } catch (error) {
    console.error("获取任务失败:", error);
    tasks.value = [];
  }
};

const viewAnnotation = async (taskId) => {
  try {
    const userInfo = JSON.parse(localStorage.getItem('userInfo'));
    const response = await fetch(`/api/annotation/tasks/${taskId}/details`, {
      headers: {
        'X-User-Id': userInfo.id.toString()
      }
    });
    
    const data = await response.json();
    if (data.success) {
      currentTaskId.value = taskId;
      
      // 处理新格式数据
      const annotations = data.annotations || {};
      currentAnnotation.value = {
        entity_name: annotations.entity_name || '',
        entity_type: annotations.entity_type || '其他',
        description: annotations.description || '',
        source: annotations.source || '',
        period_era: annotations.period_era || '',
        geo_coordinates: annotations.geo_coordinates || '',
        cultural_region: annotations.cultural_region || '',
        style_features: annotations.style_features || '',
        cultural_value: annotations.cultural_value || '',
        related_images_url: annotations.related_images_url || '',
        digital_resource_link: annotations.digital_resource_link || '',
        // 兼容旧格式
        entities: annotations.entities || []
      };
      
      showAnnotationModal.value = true;
    } else {
      alert('获取标注详情失败: ' + data.message);
    }
  } catch (error) {
    console.error('获取标注详情失败:', error);
    alert('获取标注详情失败');
  }
};

const editAnnotation = (taskId) => {
  viewAnnotation(taskId);
};

const closeAnnotationModal = () => {
  showAnnotationModal.value = false;
  currentTaskId.value = null;
  currentAnnotation.value = {
    entity_name: '',
    entity_type: '其他',
    description: '',
    source: '',
    period_era: '',
    geo_coordinates: '',
    cultural_region: '',
    style_features: '',
    cultural_value: '',
    related_images_url: '',
    digital_resource_link: '',
    entities: []
  };
};

const approveAnnotation = async (taskId) => {
  if (!confirm('确定要审核通过此标注吗？通过后数据将迁移到正式表。')) {
    return;
  }
  
  try {
    const userInfo = JSON.parse(localStorage.getItem('userInfo'));
    const response = await fetch(`/api/annotation/tasks/${taskId}/approve`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-User-Id': userInfo.id.toString()
      }
    });
    
    const data = await response.json();
    if (data.success) {
      alert('标注已审核通过，数据已迁移');
      fetchTasks();
    } else {
      alert('审核失败: ' + data.message);
    }
  } catch (error) {
    console.error('审核失败:', error);
    alert('审核失败');
  }
};

const rejectAnnotation = async (taskId) => {
  const reason = prompt('请输入驳回原因：');
  if (!reason) {
    return;
  }
  
  try {
    const userInfo = JSON.parse(localStorage.getItem('userInfo'));
    const response = await fetch(`/api/annotation/tasks/${taskId}/reject`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-User-Id': userInfo.id.toString()
      },
      body: JSON.stringify({ reason })
    });
    
    const data = await response.json();
    if (data.success) {
      alert('标注已驳回');
      fetchTasks();
    } else {
      alert('驳回失败: ' + data.message);
    }
  } catch (error) {
    console.error('驳回失败:', error);
    alert('驳回失败');
  }
};

const saveAnnotation = async () => {
  if (!currentTaskId.value) return;
  
  // 验证必填字段
  if (!currentAnnotation.value.entity_name || !currentAnnotation.value.entity_name.trim()) {
    alert('请输入实体名称');
    return;
  }
  
  try {
    const userInfo = JSON.parse(localStorage.getItem('userInfo'));
    
    // 构建请求数据（使用新格式）
    const annotationData = {
      entity_name: currentAnnotation.value.entity_name.trim(),
      entity_type: currentAnnotation.value.entity_type || '其他',
      description: currentAnnotation.value.description || '',
      source: currentAnnotation.value.source || '',
      period_era: currentAnnotation.value.period_era || '',
      geo_coordinates: currentAnnotation.value.geo_coordinates || '',
      cultural_region: currentAnnotation.value.cultural_region || '',
      style_features: currentAnnotation.value.style_features || '',
      cultural_value: currentAnnotation.value.cultural_value || '',
      related_images_url: currentAnnotation.value.related_images_url || '',
      digital_resource_link: currentAnnotation.value.digital_resource_link || ''
    };
    
    const response = await fetch(`/api/annotation/tasks/${currentTaskId.value}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'X-User-Id': userInfo.id.toString()
      },
      body: JSON.stringify(annotationData)
    });
    
    const data = await response.json();
    if (data.success) {
      alert('标注已保存');
      closeAnnotationModal();
      fetchTasks();
    } else {
      alert('保存失败: ' + data.message);
    }
  } catch (error) {
    console.error('保存标注失败:', error);
    alert('保存失败');
  }
};
</script>

<style scoped>
.annotation-container {
  max-width: 1000px;
  margin: 20px auto;
  padding: 0 20px;
}

.filter-bar {
  margin-bottom: 20px;
}

.filter-bar select {
  padding: 8px;
  border-radius: 4px;
  border: 1px solid #ddd;
}

.tasks-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;
}

.task-card {
  background: white;
  border-radius: 8px;
  padding: 15px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.task-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.task-status {
  padding: 3px 8px;
  border-radius: 4px;
  font-size: 12px;
  color: white;
}

.task-status.待标注 {
  background-color: #f5a623;
}

.task-status.已标注 {
  background-color: #42b983;
}

.task-info p {
  margin: 5px 0;
  font-size: 14px;
}

.task-actions {
  margin-top: 15px;
  display: flex;
  gap: 10px;
}

.task-actions button {
  padding: 6px 12px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  background-color: #42b983;
  color: white;
}

.task-actions button:hover {
  background-color: #359e75;
}

/* 模态框样式 */
.modal {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(0,0,0,0.5);
  display: flex;
  justify-content: center;
  align-items: center;
}

.modal-content {
  background-color: white;
  padding: 20px;
  border-radius: 8px;
  width: 90%;
  max-width: 600px;
  position: relative;
}

.close-btn {
  position: absolute;
  top: 15px;
  right: 20px;
  font-size: 24px;
  cursor: pointer;
}

.entity-item {
  display: flex;
  gap: 10px;
  margin-bottom: 10px;
  align-items: center;
}

.entity-item input, .entity-item select {
  padding: 6px;
  flex: 1;
}

.entity-item button {
  padding: 6px 10px;
  background-color: #ff4d4f;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.add-entity-btn {
  margin: 10px 0;
  padding: 8px 12px;
  background-color: #1890ff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.annotation-notes {
  margin: 15px 0;
}

.annotation-notes textarea {
  width: 100%;
  min-height: 100px;
  padding: 8px;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.save-annotation-btn {
  padding: 10px 15px;
  background-color: #42b983;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 16px;
}

.form-group {
  margin-bottom: 15px;
}

.form-group label {
  display: block;
  margin-bottom: 5px;
  font-weight: 500;
  color: #333;
}

.form-group input[type="text"],
.form-group textarea,
.form-group select {
  width: 100%;
  padding: 8px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 14px;
}

.form-group textarea {
  resize: vertical;
  min-height: 60px;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 15px;
}

.annotation-actions {
  display: flex;
  gap: 10px;
  margin-top: 20px;
}

.save-annotation-btn:hover {
  background-color: #359e75;
}

.cancel-btn {
  background-color: #f5f5f5;
  color: #333;
  border: 1px solid #ddd;
  padding: 10px 20px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
}

.cancel-btn:hover {
  background-color: #e8e8e8;
}

.approve-btn {
  background-color: #52c41a;
  color: white;
}

.approve-btn:hover {
  background-color: #73d13d;
}

.reject-btn {
  background-color: #ff4d4f;
  color: white;
}

.reject-btn:hover {
  background-color: #ff7875;
}
</style>