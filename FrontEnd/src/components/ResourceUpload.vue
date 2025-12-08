<template>
  <div class="upload-container">
    <h2>资源上传</h2>
    <form @submit.prevent="handleUpload">
      <div class="form-group">
        <label for="resourceFile">选择文件</label>
        <input 
          type="file" 
          id="resourceFile" 
          @change="handleFileChange" 
          required
        >
      </div>
      
      <div class="form-group">
        <label for="resourceType">资源类型</label>
        <select id="resourceType" v-model="resourceType" required>
          <option value="">请选择类型</option>
          <option value="文本">文本</option>
          <option value="图像">图像</option>
        </select>
      </div>
      
      <button type="submit" class="upload-btn">上传并提交AI标注</button>
    </form>
    
    <div v-if="message" :class="['message', message.includes('失败') ? 'error' : '']">{{ message }}</div>
  </div>
</template>

<script setup>
import { ref } from 'vue';

const resourceFile = ref(null);
const resourceType = ref('');
const message = ref('');

const handleFileChange = (e) => {
  const file = e.target.files[0];
  if (!file) {
    resourceFile.value = null;
    return;
  }
  
  // 验证文件类型：只允许图片或文本文件
  const fileName = file.name.toLowerCase();
  const fileExtension = fileName.split('.').pop();
  
  // 图片文件扩展名
  const imageExtensions = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'svg'];
  // 文本文件扩展名
  const textExtensions = ['txt', 'md', 'doc', 'docx', 'pdf'];
  
  const isImage = imageExtensions.includes(fileExtension);
  const isText = textExtensions.includes(fileExtension);
  
  if (!isImage && !isText) {
    message.value = `不支持的文件类型：${fileExtension}。仅支持图片（${imageExtensions.join(', ')}）或文本（${textExtensions.join(', ')}）文件`;
    e.target.value = ''; // 清空文件选择
    resourceFile.value = null;
    return;
  }
  
  // 根据文件类型自动设置资源类型
  if (isImage && resourceType.value !== '图像') {
    resourceType.value = '图像';
  } else if (isText && resourceType.value !== '文本') {
    resourceType.value = '文本';
  }
  
  resourceFile.value = file;
  message.value = ''; // 清空之前的错误消息
};

const handleUpload = async () => {
  if (!resourceFile.value || !resourceType.value) {
    message.value = "请选择文件并指定资源类型";
    return;
  }
  
  // 再次验证文件类型（双重验证）
  const fileName = resourceFile.value.name.toLowerCase();
  const fileExtension = fileName.split('.').pop();
  const imageExtensions = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'svg'];
  const textExtensions = ['txt', 'md', 'doc', 'docx', 'pdf'];
  const isImage = imageExtensions.includes(fileExtension);
  const isText = textExtensions.includes(fileExtension);
  
  if (!isImage && !isText) {
    message.value = `不支持的文件类型：${fileExtension}。仅支持图片或文本文件`;
    return;
  }
  
  // 验证资源类型与文件类型是否匹配
  if (resourceType.value === '图像' && !isImage) {
    message.value = "选择的文件不是图片格式，请重新选择";
    return;
  }
  if (resourceType.value === '文本' && !isText) {
    message.value = "选择的文件不是文本格式，请重新选择";
    return;
  }
  
  // 模拟登录状态，实际项目中应从全局状态获取
  const userInfo = JSON.parse(localStorage.getItem('userInfo'));
  if (!userInfo) {
    message.value = "请先登录";
    return;
  }
  
  const formData = new FormData();
  formData.append('file', resourceFile.value);
  formData.append('resourceType', resourceType.value);
  formData.append('userId', userInfo.id);
  
  try {
    const response = await fetch('/api/upload', {
      method: 'POST',
      body: formData
    });
    
    const result = await response.json();
    
    if (result.success) {
      message.value = result.message || `文件 "${resourceFile.value.name}" 上传成功，已提交AI标注任务`;
      
      // 清空表单
      resourceFile.value = null;
      resourceType.value = '';
      document.getElementById('resourceFile').value = '';
    } else {
      message.value = result.message || `上传失败: ${result.error || '未知错误'}`;
    }
  } catch (error) {
    message.value = `上传失败: ${error.message}`;
    console.error('上传错误:', error);
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