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
          <option value="音频">音频</option>
          <option value="视频">视频</option>
        </select>
      </div>
      
      <button type="submit" class="upload-btn">上传并提交AI标注</button>
    </form>
    
    <div v-if="message" class="message">{{ message }}</div>
  </div>
</template>

<script setup>
import { ref } from 'vue';

const resourceFile = ref(null);
const resourceType = ref('');
const message = ref('');

const handleFileChange = (e) => {
  resourceFile.value = e.target.files[0];
};

const handleUpload = async () => {
  if (!resourceFile.value || !resourceType.value) {
    message.value = "请选择文件并指定资源类型";
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
    // 实际项目中替换为真实API地址
    // const response = await fetch('/api/upload', {
    //   method: 'POST',
    //   body: formData
    // });
    
    // 模拟API调用成功
    message.value = `文件 "${resourceFile.value.name}" 上传成功，已提交AI标注任务`;
    
    // 清空表单
    resourceFile.value = null;
    resourceType.value = '';
    document.getElementById('resourceFile').value = '';
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

.message {
  margin-top: 15px;
  padding: 10px;
  border-radius: 4px;
  color: #fff;
  background-color: #42b983;
}
</style>