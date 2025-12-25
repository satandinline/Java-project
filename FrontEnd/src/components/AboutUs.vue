<template>
  <div class="about-us-container">
    <div class="about-header">
      <h1>关于我们</h1>
      <button class="back-btn" @click="goBack">← 返回</button>
    </div>

    <div class="about-content">
      <!-- 系统介绍 -->
      <section class="about-section">
        <h2>系统介绍</h2>
        <div class="section-content">
          <p>
            公共文化资源管理系统是一个基于AI的智能文化资源管理平台，致力于传统文化的数字化保存、传播和创新。
          </p>
          <p>
            系统集成了文化资源爬取、智能检索、AI生成、用户标注等多项功能，为文化资源的数字化管理提供了完整的解决方案。
          </p>
          
          <h3>核心功能</h3>
          <ul>
            <li><strong>文化资源管理</strong>：支持文化资源的爬取、存储、检索和管理</li>
            <li><strong>智能检索</strong>：提供全文检索和AI语义检索两种方式</li>
            <li><strong>AIGC生成</strong>：基于大模型的文字和图片生成功能</li>
            <li><strong>用户标注</strong>：支持用户上传资源并进行AI辅助标注</li>
            <li><strong>多模态搜索</strong>：支持文本和图片的跨模态检索</li>
            <li><strong>评论互动</strong>：用户可以对资源进行评论、点赞和回复</li>
          </ul>

          <h3>技术架构</h3>
          <ul>
            <li><strong>前端</strong>：Vue.js 3 + Vite</li>
            <li><strong>后端</strong>：Python Flask + MySQL</li>
            <li><strong>AI模型</strong>：通义千问、OpenAI GPT-4o-mini、DeepSeek、火山引擎</li>
            <li><strong>向量数据库</strong>：ChromaDB</li>
            <li><strong>RAG系统</strong>：检索增强生成，提升AI回答质量</li>
          </ul>
        </div>
      </section>

      <!-- 用户使用手册 -->
      <section class="about-section">
        <h2>用户使用手册</h2>
        <div class="section-content">
          <h3>1. 用户注册与登录</h3>
          <ul>
            <li>系统会自动生成8-10位数字账号，请妥善保管</li>
            <li>支持设置昵称、头像、个人签名和安全问题</li>
            <li>忘记密码可通过安全问题找回</li>
          </ul>

          <h3>2. 首页功能</h3>
          <ul>
            <li><strong>3D轮播</strong>：浏览精选文化资源视频</li>
            <li><strong>资源浏览</strong>：查看文化资源卡片，点击查看详情</li>
            <li><strong>全文检索</strong>：直接关键词匹配搜索</li>
            <li><strong>AI检索</strong>：使用AI理解自然语言需求进行语义搜索</li>
          </ul>

          <h3>3. AIGC功能</h3>
          <ul>
            <li><strong>文字AIGC</strong>：
              <ul>
                <li>输入问题或需求，AI会基于RAG检索生成回答</li>
                <li>支持上传图片，AI会理解图片内容</li>
                <li>无输入时自动生成传统文化故事</li>
                <li>支持多轮对话，查看历史会话</li>
              </ul>
            </li>
            <li><strong>图片AIGC</strong>：
              <ul>
                <li>输入描述，AI会生成对应的图片</li>
                <li>支持上传参考图片</li>
                <li>无输入时自动生成故事并生成连环画</li>
                <li>生成的图片会保存到个人图库</li>
              </ul>
            </li>
          </ul>

          <h3>4. 资源上传与标注</h3>
          <ul>
            <li>用户可以上传文本、图片等文化资源</li>
            <li>系统会自动进行AI标注，提取实体信息</li>
            <li>管理员可以审核和编辑标注结果</li>
            <li>支持暂停和恢复AI标注任务</li>
          </ul>

          <h3>5. 图文互搜</h3>
          <ul>
            <li>输入文本或上传图片进行搜索</li>
            <li>系统会理解图片内容并转换为文本描述</li>
            <li>返回相关的文本和图片资源</li>
          </ul>

          <h3>6. 评论与互动</h3>
          <ul>
            <li>在资源详情页可以发表评论</li>
            <li>支持对评论进行点赞和回复</li>
            <li>收到点赞或回复时会收到消息通知</li>
            <li>在AIGC页面可以查看消息通知</li>
          </ul>

          <h3>7. 数据大屏（管理员）</h3>
          <ul>
            <li>查看系统访问统计</li>
            <li>查看AIGC使用情况</li>
            <li>查看趋势图表</li>
          </ul>

          <h3>8. 用户管理（超级管理员）</h3>
          <ul>
            <li>查看所有用户列表</li>
            <li>修改用户角色</li>
            <li>管理用户权限</li>
          </ul>
        </div>
      </section>

      <!-- 系统要求 -->
      <section class="about-section">
        <h2>系统要求</h2>
        <div class="section-content">
          <h3>浏览器支持</h3>
          <ul>
            <li>Chrome 90+</li>
            <li>Firefox 88+</li>
            <li>Edge 90+</li>
            <li>Safari 14+</li>
          </ul>

          <h3>网络要求</h3>
          <ul>
            <li>稳定的网络连接</li>
            <li>建议带宽：2Mbps以上</li>
          </ul>
        </div>
      </section>

      <!-- 联系方式 -->
      <section class="about-section">
        <h2>联系我们</h2>
        <div class="section-content">
          <p>如有问题或建议，请联系系统管理员。</p>
          <p>系统版本：v1.0.0</p>
          <p>最后更新：2025年</p>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router';

const router = useRouter();

const goBack = () => {
  router.back();
};
</script>

<style scoped>
.about-us-container {
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 20px;
}

.about-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 30px;
  background: white;
  padding: 20px 30px;
  border-radius: 10px;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
}

.about-header h1 {
  margin: 0;
  color: #333;
  font-size: 28px;
}

.back-btn {
  background: #667eea;
  color: white;
  border: none;
  padding: 10px 20px;
  border-radius: 5px;
  cursor: pointer;
  font-size: 16px;
  transition: background 0.3s;
}

.back-btn:hover {
  background: #5568d3;
}

.about-content {
  max-width: 1000px;
  margin: 0 auto;
}

.about-section {
  background: white;
  padding: 30px;
  margin-bottom: 20px;
  border-radius: 10px;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
}

.about-section h2 {
  color: #667eea;
  margin-top: 0;
  margin-bottom: 20px;
  font-size: 24px;
  border-bottom: 2px solid #667eea;
  padding-bottom: 10px;
}

.about-section h3 {
  color: #555;
  margin-top: 25px;
  margin-bottom: 15px;
  font-size: 18px;
}

.section-content {
  line-height: 1.8;
  color: #333;
}

.section-content p {
  margin-bottom: 15px;
}

.section-content ul {
  margin-left: 20px;
  margin-bottom: 20px;
}

.section-content li {
  margin-bottom: 10px;
}

.section-content ul ul {
  margin-top: 10px;
  margin-left: 30px;
}

.section-content strong {
  color: #667eea;
}
</style>

