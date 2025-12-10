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
        </div>
      </div>
    </div>
    
    <!-- 标注编辑弹窗 -->
    <div class="modal" v-if="showAnnotationModal">
      <div class="modal-content">
        <span class="close-btn" @click="closeAnnotationModal">&times;</span>
        <h3>标注编辑</h3>
        
        <div class="annotation-content">
          <div v-if="currentAnnotation && currentAnnotation.entities">
            <h4>实体标注:</h4>
            <div class="entities-list">
              <div class="entity-item" v-for="(entity, index) in currentAnnotation.entities" :key="index">
                <input 
                  type="text" 
                  v-model="entity.name" 
                  placeholder="实体名称"
                >
                <select v-model="entity.type">
                  <option value="人物">人物</option>
                  <option value="地点">地点</option>
                  <option value="事件">事件</option>
                  <option value="物品">物品</option>
                  <option value="其他">其他</option>
                </select>
                <button @click="removeEntity(index)">删除</button>
              </div>
            </div>
            
            <button class="add-entity-btn" @click="addEntity">添加实体</button>
            
            <div class="annotation-notes">
              <label>标注说明:</label>
              <textarea 
                v-model="currentAnnotation.description"
                placeholder="添加标注说明..."
              ></textarea>
            </div>
            
            <button class="save-annotation-btn" @click="saveAnnotation">保存标注</button>
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
const currentAnnotation = ref({
  entities: [],
  description: ''
});

onMounted(() => {
  fetchTasks();
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
      currentAnnotation.value = data.annotations || { entities: [], description: '' };
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
  currentAnnotation.value = { entities: [], description: '' };
};

const addEntity = () => {
  currentAnnotation.value.entities.push({
    name: '',
    type: '其他'
  });
};

const removeEntity = (index) => {
  currentAnnotation.value.entities.splice(index, 1);
};

const saveAnnotation = async () => {
  if (!currentTaskId.value) return;
  
  try {
    const userInfo = JSON.parse(localStorage.getItem('userInfo'));
    const response = await fetch(`/api/annotation/tasks/${currentTaskId.value}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'X-User-Id': userInfo.id.toString()
      },
      body: JSON.stringify(currentAnnotation.value)
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
</style>