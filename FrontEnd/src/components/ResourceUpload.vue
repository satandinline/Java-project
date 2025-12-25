<template>
  <div class="upload-container">
    <h2>资源上传</h2>
    <form @submit.prevent="handleUpload">
      <div class="form-group">
        <label for="resourceType">资源类型</label>
        <select id="resourceType" v-model="resourceType" @change="handleResourceTypeChange" required>
          <option value="">请选择类型</option>
          <option value="文本">文本</option>
          <option value="图像">图像</option>
        </select>
      </div>
      
      <!-- 文本类型：支持直接输入或文件上传 -->
      <div v-if="resourceType === '文本'" class="form-group">
        <label>上传方式</label>
        <div class="radio-group">
          <label class="radio-label">
            <input 
              type="radio" 
              v-model="uploadMode" 
              value="text"
              @change="handleUploadModeChange"
            >
            <span>直接输入文本</span>
          </label>
          <label class="radio-label">
            <input 
              type="radio" 
              v-model="uploadMode" 
              value="file"
              @change="handleUploadModeChange"
            >
            <span>上传文件（Word/PDF）</span>
          </label>
        </div>
      </div>
      
      <!-- 文本直接输入 -->
      <div v-if="resourceType === '文本' && uploadMode === 'text'" class="form-group">
        <label for="textContent">文本内容 <span class="required">*</span></label>
        <textarea 
          id="textContent"
          v-model="textContent"
          placeholder="请输入文本内容..."
          rows="10"
          required
        ></textarea>
        <p class="hint">提示：文本内容将直接用于AI标注</p>
      </div>
      
      <!-- 文件上传（文本或图像） -->
      <div v-if="(resourceType === '文本' && uploadMode === 'file') || resourceType === '图像'" class="form-group">
        <label for="resourceFile">
          {{ resourceType === '文本' ? '选择文件（Word文档或PDF）' : '选择图片（JPG或PNG）' }}
          <span class="required">*</span>
        </label>
        <input 
          type="file" 
          id="resourceFile" 
          @change="handleFileChange"
          :accept="resourceType === '文本' ? '.doc,.docx,.pdf' : '.jpg,.jpeg,.png'"
          :required="(resourceType === '文本' && uploadMode === 'file') || resourceType === '图像'"
        >
        <p class="hint">
          {{ resourceType === '文本' ? '支持格式：Word文档（.doc, .docx）或PDF（.pdf）' : '支持格式：JPG（.jpg）或PNG（.png）' }}
        </p>
      </div>
      
      <div class="form-group">
        <label class="checkbox-label">
          <input 
            type="checkbox" 
            v-model="enableAnnotation"
            @change="handleAnnotationToggle"
          >
          <span>上传时进行标注（可选）</span>
        </label>
      </div>
      
      <!-- 标注表单（可折叠） -->
      <div v-if="enableAnnotation" class="annotation-section">
        <h3>标注信息</h3>
        
        <div class="form-group">
          <label>实体名称 <span class="required">*</span></label>
          <input 
            type="text" 
            v-model="annotation.entity_name" 
            placeholder="请输入实体名称"
            required
          >
        </div>
        
        <div class="form-group">
          <label>实体类型 <span class="required">*</span></label>
          <select v-model="annotation.entity_type">
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
            v-model="annotation.description"
            placeholder="请输入实体描述..."
            rows="3"
          ></textarea>
        </div>
        
        <div class="form-group">
          <label>来源</label>
          <input 
            type="text" 
            v-model="annotation.source" 
            placeholder="请输入来源信息"
          >
        </div>
        
        <div class="form-row">
          <div class="form-group">
            <label>时期年代</label>
            <input 
              type="text" 
              v-model="annotation.period_era" 
              placeholder="例如：唐代、明清"
            >
          </div>
          
          <div class="form-group">
            <label>地理坐标</label>
            <input 
              type="text" 
              v-model="annotation.geo_coordinates" 
              placeholder="例如：经度,纬度"
            >
          </div>
        </div>
        
        <div class="form-group">
          <label>文化区域</label>
          <input 
            type="text" 
            v-model="annotation.cultural_region" 
            placeholder="例如：华北、江南"
          >
        </div>
        
        <div class="form-group">
          <label>风格特征</label>
          <textarea 
            v-model="annotation.style_features"
            placeholder="请输入风格特征..."
            rows="2"
          ></textarea>
        </div>
        
        <div class="form-group">
          <label>文化价值</label>
          <textarea 
            v-model="annotation.cultural_value"
            placeholder="请输入文化价值..."
            rows="2"
          ></textarea>
        </div>
        
        <div class="form-group">
          <label>相关图像链接</label>
          <input 
            type="text" 
            v-model="annotation.related_images_url" 
            placeholder="请输入图像URL"
          >
        </div>
        
        <div class="form-group">
          <label>数字资源链接</label>
          <input 
            type="text" 
            v-model="annotation.digital_resource_link" 
            placeholder="请输入数字资源URL"
          >
        </div>
      </div>
      
      <button type="submit" class="upload-btn">
        {{ enableAnnotation ? '上传并保存标注' : '上传并提交AI标注' }}
      </button>
    </form>
    
    <div v-if="message" :class="['message', message.includes('失败') ? 'error' : '']">{{ message }}</div>
  </div>
</template>

<script setup>
import { ref } from 'vue';

const resourceFile = ref(null);
const resourceType = ref('');
const uploadMode = ref('text'); // 'text' 或 'file'
const textContent = ref('');
const message = ref('');
const enableAnnotation = ref(false);
const annotation = ref({
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
  digital_resource_link: ''
});

const handleResourceTypeChange = () => {
  // 切换资源类型时重置上传模式和文件
  if (resourceType.value === '文本') {
    uploadMode.value = 'text';
  } else {
    uploadMode.value = 'file';
  }
  resourceFile.value = null;
  textContent.value = '';
  message.value = '';
};

const handleUploadModeChange = () => {
  // 切换上传模式时清空文件选择
  resourceFile.value = null;
  textContent.value = '';
  message.value = '';
};

const handleFileChange = (e) => {
  const file = e.target.files[0];
  if (!file) {
    resourceFile.value = null;
    return;
  }
  
  // 验证文件类型
  const fileName = file.name.toLowerCase();
  const fileExtension = fileName.split('.').pop();
  
  if (resourceType.value === '文本') {
    // 文本类型只允许.doc, .docx, .pdf
    const textExtensions = ['doc', 'docx', 'pdf'];
    if (!textExtensions.includes(fileExtension)) {
      message.value = `文本类型只支持Word文档（.doc, .docx）或PDF（.pdf），当前文件类型：${fileExtension}`;
      e.target.value = '';
      resourceFile.value = null;
      return;
    }
  } else if (resourceType.value === '图像') {
    // 图像类型只允许.jpg, .png
    const imageExtensions = ['jpg', 'jpeg', 'png'];
    if (!imageExtensions.includes(fileExtension)) {
      message.value = `图像类型只支持JPG（.jpg）或PNG（.png），当前文件类型：${fileExtension}`;
      e.target.value = '';
      resourceFile.value = null;
      return;
    }
  }
  
  resourceFile.value = file;
  message.value = ''; // 清空之前的错误消息
};

const handleAnnotationToggle = () => {
  if (!enableAnnotation.value) {
    // 如果取消标注，重置标注表单
    annotation.value = {
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
      digital_resource_link: ''
    };
  }
};

const handleUpload = async () => {
  if (!resourceType.value) {
    message.value = "请选择资源类型";
    return;
  }
  
  // 验证输入内容
  if (resourceType.value === '文本') {
    if (uploadMode.value === 'text') {
      // 文本直接输入模式
      if (!textContent.value || !textContent.value.trim()) {
        message.value = "请输入文本内容";
        return;
      }
    } else {
      // 文件上传模式
      if (!resourceFile.value) {
        message.value = "请选择要上传的文件";
        return;
      }
      // 验证文件类型
      const fileName = resourceFile.value.name.toLowerCase();
      const fileExtension = fileName.split('.').pop();
      const textExtensions = ['doc', 'docx', 'pdf'];
      if (!textExtensions.includes(fileExtension)) {
        message.value = `文本类型只支持Word文档（.doc, .docx）或PDF（.pdf），当前文件类型：${fileExtension}`;
        return;
      }
    }
  } else if (resourceType.value === '图像') {
    if (!resourceFile.value) {
      message.value = "请选择要上传的图片";
      return;
    }
    // 验证文件类型
    const fileName = resourceFile.value.name.toLowerCase();
    const fileExtension = fileName.split('.').pop();
    const imageExtensions = ['jpg', 'jpeg', 'png'];
    if (!imageExtensions.includes(fileExtension)) {
      message.value = `图像类型只支持JPG（.jpg）或PNG（.png），当前文件类型：${fileExtension}`;
      return;
    }
  }
  
  // 如果启用了标注，验证必填字段
  if (enableAnnotation.value) {
    if (!annotation.value.entity_name || !annotation.value.entity_name.trim()) {
      message.value = "请输入实体名称";
      return;
    }
  }
  
  // 从sessionStorage获取用户信息（与App.vue保持一致）
  const userInfoStr = sessionStorage.getItem('userInfo');
  if (!userInfoStr) {
    message.value = "请先登录";
    return;
  }
  
  let userInfo;
  try {
    userInfo = JSON.parse(userInfoStr);
  } catch (e) {
    message.value = "用户信息无效，请重新登录";
    return;
  }
  
  const formData = new FormData();
  formData.append('resourceType', resourceType.value);
  formData.append('userId', userInfo.id);
  
  // 根据上传模式添加内容
  if (resourceType.value === '文本' && uploadMode.value === 'text') {
    // 文本直接输入
    formData.append('textContent', textContent.value.trim());
  } else {
    // 文件上传
    formData.append('file', resourceFile.value);
  }
  
  // 如果启用了标注，添加标注数据
  if (enableAnnotation.value) {
    const annotationData = {
      entity_name: annotation.value.entity_name.trim(),
      entity_type: annotation.value.entity_type || '其他',
      description: annotation.value.description || '',
      source: annotation.value.source || '',
      period_era: annotation.value.period_era || '',
      geo_coordinates: annotation.value.geo_coordinates || '',
      cultural_region: annotation.value.cultural_region || '',
      style_features: annotation.value.style_features || '',
      cultural_value: annotation.value.cultural_value || '',
      related_images_url: annotation.value.related_images_url || '',
      digital_resource_link: annotation.value.digital_resource_link || ''
    };
    formData.append('annotation', JSON.stringify(annotationData));
  }
  
  try {
    const response = await fetch('/api/upload', {
      method: 'POST',
      body: formData
    });
    
    const result = await response.json();
    
    if (result.success) {
      if (enableAnnotation.value) {
        message.value = result.message || `文件 "${resourceFile.value.name}" 上传成功，用户标注已保存`;
      } else {
        message.value = result.message || `文件 "${resourceFile.value.name}" 上传成功，已提交AI标注任务`;
      }
      
      // 清空表单
      resourceFile.value = null;
      resourceType.value = '';
      uploadMode.value = 'text';
      textContent.value = '';
      enableAnnotation.value = false;
      annotation.value = {
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
        digital_resource_link: ''
      };
      const fileInput = document.getElementById('resourceFile');
      if (fileInput) {
        fileInput.value = '';
      }
    } else {
      message.value = result.message || `上传失败: ${result.error || '未知错误'}`;
    }
  } catch (error) {
    message.value = `上传失败: ${error.message}`;
  }
};
</script>

<style scoped>
.upload-container {
  max-width: 600px;
  margin: 20px auto;
  padding: 20px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.form-group {
  margin-bottom: 15px;
}

label {
  display: block;
  margin-bottom: 5px;
  font-weight: 500;
}

input[type="file"], select {
  width: 100%;
  padding: 8px;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.upload-btn {
  background-color: #42b983;
  color: white;
  border: none;
  padding: 10px 15px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 16px;
}

.upload-btn:hover {
  background-color: #359e75;
}

.radio-group {
  display: flex;
  gap: 20px;
  margin-top: 5px;
}

.radio-label {
  display: flex;
  align-items: center;
  gap: 5px;
  cursor: pointer;
}

.radio-label input[type="radio"] {
  width: auto;
  margin: 0;
}

.hint {
  margin-top: 5px;
  font-size: 12px;
  color: #666;
}

textarea {
  width: 100%;
  padding: 8px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-family: inherit;
  font-size: 14px;
  resize: vertical;
}

.message {
  margin-top: 15px;
  padding: 10px;
  border-radius: 4px;
  color: #fff;
  background-color: #42b983;
}

.message.error {
  background-color: #f56c6c;
}
</style>