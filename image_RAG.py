import os
import requests
import time
import json
import warnings
from typing import Dict, Optional, List, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime
import urllib3
from typing import Tuple
from dotenv import load_dotenv
from urllib.parse import urlparse

# 忽略无关警告
warnings.filterwarnings('ignore', category=UserWarning)
warnings.filterwarnings('ignore', category=urllib3.exceptions.InsecureRequestWarning)

# 新增指定自定义.env文件名（.env）
load_dotenv(dotenv_path=".env", override=True)


# ===================== 核心配置（修复默认尺寸+从环境变量读取密钥）=====================
@dataclass
class AIGCConfig:
    """AIGC功能核心配置（集中管理，便于部署调整）"""
    # 默认模型（火山引擎Seedream 4.0，已验证支持1024x1024）
    default_model: str = "volc_seedream"
    # 模型配置（从环境变量读取密钥，移除硬编码）
    model_configs: Dict = field(default_factory=lambda: {
        "volc_seedream": {
            "name": "火山引擎Seedream 4.0",
            "api_url": "https://ark.cn-beijing.volces.com/api/v3/images/generations",
            "api_key": os.getenv("VOLC_SEEDREAM_API_KEY"),  # 从.env读取火山引擎密钥
            "model_id": "doubao-seedream-4-0-250828",
            "image_size": "1024x1024",  # 回退到模型支持的默认尺寸
            "supported_sizes": ["1024x1024", "2048x2048"],  # 模型支持的尺寸列表（关键）
            "timeout": 90,
            "max_retries": 2,
            "request_format": "volc"
        },
        "ali_sd_xl": {
            "name": "阿里云Stable Diffusion XL",
            "api_url": "https://dashscope.aliyuncs.com/api/v1/services/aigc/image-generation/generation",
            "api_key": os.getenv("DASHSCOPE_API_KEY"),  # 从.env读取阿里云密钥
            "model_id": "stable-diffusion-xl",
            "image_size": "1024x1024",
            "supported_sizes": ["512x512", "1024x1024", "2048x2048"],
            "timeout": 120,
            "max_retries": 2,
            "request_format": "aliyun"
        }
    })
    # 提示词模板（移除固定尺寸限制，避免冲突）
    prompt_template: str = """
    主题：{prompt}，风格：{style}
    补充参考信息：{retrieval_info}
    要求：高清分辨率，细节丰富，色彩鲜明，符合主题文化内涵，
          构图合理，无多余元素，视觉冲击力强，适合商业使用
    """
    # 日志配置
    log_dir: str = "aigc_logs"
    # 存储配置
    save_local: bool = True  # 修改为True，确保本地保存功能开启
    local_save_dir: str = "images"  # 修改为images文件夹
    # 检索功能开关
    enable_retrieval: bool = False
    # 检索模块调用函数占位符
    retrieval_func: Optional[Callable[[str, str], str]] = None


# 初始化配置
config = AIGCConfig()


# ===================== 工具函数（不变）=====================
def init_dirs():
    os.makedirs(config.log_dir, exist_ok=True)
    if config.save_local:
        os.makedirs(config.local_save_dir, exist_ok=True)


def log_info(message: str):
    log_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_content = f"[{log_time}] [INFO] {message}\n"
    print(log_content, end="")
    with open(os.path.join(config.log_dir, "aigc.log"), "a", encoding="utf-8") as f:
        f.write(log_content)


def log_error(message: str):
    log_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_content = f"[{log_time}] [ERROR] {message}\n"
    print(log_content, end="")
    with open(os.path.join(config.log_dir, "aigc_error.log"), "a", encoding="utf-8") as f:
        f.write(log_content)


def save_image_local(image_url: str, prompt: str, model_name: str, image_dir: str) -> str:
    if not config.save_local:
        return ""
    try:
        response = requests.get(image_url, timeout=30, verify=False)
        response.raise_for_status()
        
        # 查找当前目录中的最大编号
        existing_files = []
        for filename in os.listdir(image_dir):
            if os.path.isfile(os.path.join(image_dir, filename)):
                name_part = filename.split('.')[0]
                if name_part.isdigit():
                    existing_files.append(int(name_part))
        
        # 计算下一个编号
        next_number = max(existing_files) + 1 if existing_files else 1
        
        # 尝试从URL获取扩展名
        file_extension = ".jpg"  # 默认扩展名
        parsed_url = urlparse(image_url)
        original_filename = os.path.basename(parsed_url.path)
        if '.' in original_filename:
            ext = '.' + original_filename.split('.')[-1]
            if ext.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                file_extension = ext
        
        file_name = f"{next_number:04d}{file_extension}"
        file_path = os.path.join(image_dir, file_name)
        
        with open(file_path, "wb") as f:
            f.write(response.content)
        log_info(f"图片已保存到本地：{file_path}")
        return file_path
    except Exception as e:
        log_error(f"本地保存图片失败：{str(e)}")
        return ""


# ===================== 检索功能占位符（不变）=====================
def default_retrieval_func(prompt: str, style: str) -> str:
    log_info(f"检索功能占位符被调用，主题：{prompt}，风格：{style}（当前未启用实际检索）")
    return ""


def set_retrieval_func(retrieval_func: Callable[[str, str], str]):
    config.retrieval_func = retrieval_func
    config.enable_retrieval = True
    log_info("检索功能模块已注册，后续生图将自动调用检索补充参考信息")


# ===================== 核心AIGC功能（新增密钥校验）=====================
class ImageAIGC:
    def __init__(self):
        self.config = config
        self.default_model = config.default_model
        self.model = config.model_configs[self.default_model]

        # 新增：密钥校验（避免空密钥导致报错）
        if not self.model["api_key"]:
            raise ValueError(
                f"模型[{self.model['name']}]的API密钥未配置！\n"
                f"请在.env文件中设置 [{self.default_model.upper()}_API_KEY] 环境变量"
            )

        self.retrieval_func = self.config.retrieval_func or default_retrieval_func
        init_dirs()
        log_info("ImageAIGC功能初始化完成，默认模型：{}".format(self.model["name"]))
        log_info(f"默认生图尺寸：{self.model['image_size']}，支持尺寸：{self.model['supported_sizes']}")
        log_info(f"检索功能状态：{'已启用（占位符）' if config.enable_retrieval else '未启用'}")
        log_info(f"图片自动保存到：{config.local_save_dir}/ 目录")

    def _get_retrieval_info(self, prompt: str, style: str) -> str:
        if not self.config.enable_retrieval:
            return ""
        try:
            log_info(f"开始检索参考信息，主题：{prompt}，风格：{style}")
            retrieval_info = self.retrieval_func(prompt, style)
            if retrieval_info:
                log_info(f"检索成功，获取参考信息：{retrieval_info[:50]}...")
            else:
                log_info("检索未返回有效信息")
            return retrieval_info
        except Exception as e:
            log_error(f"检索模块调用失败：{str(e)}")
            return ""

    def _validate_image_size(self, image_size: str) -> Tuple[bool, str]:
        """校验尺寸是否被当前模型支持（新增）"""
        if not image_size:
            return True, self.model["image_size"]  # 未指定则用默认尺寸
        # 检查是否在模型支持的尺寸列表中
        if image_size in self.model["supported_sizes"]:
            return True, image_size
        else:
            warning_msg = f"尺寸{image_size}不被{self.model['name']}支持，自动使用默认尺寸{self.model['image_size']}（支持尺寸：{self.model['supported_sizes']}）"
            log_info(warning_msg)
            return False, self.model["image_size"]

    def generate_image(
            self,
            prompt: str,
            style: str,
            model_key: Optional[str] = None,
            image_size: Optional[str] = None
    ) -> str:
        """核心生图接口（修复尺寸支持+参数校验）"""
        # 1. 参数校验（确保主题和风格不为空，避免结果显示异常）
        prompt = prompt.strip() if prompt else "未指定主题"
        style = style.strip() if style else "未指定风格"
        if prompt == "未指定主题" or style == "未指定风格":
            error_msg = f"生图失败：主题（{prompt}）或风格（{style}）不能为空"
            log_error(error_msg)
            return ""

        # 2. 选择模型（切换模型时重新校验密钥）
        if model_key and model_key in self.config.model_configs:
            self.model = self.config.model_configs[model_key]
            # 切换模型后校验密钥
            if not self.model["api_key"]:
                error_msg = f"模型[{self.model['name']}]的API密钥未配置！\n请在.env文件中设置 [{model_key.upper()}_API_KEY] 环境变量"
                log_error(error_msg)
                return ""
        else:
            self.model = self.config.model_configs[self.default_model]
            log_info(f"未指定模型或模型不存在，使用默认模型：{self.model['name']}")

        # 3. 尺寸合法性校验（新增，避免无效尺寸请求）
        is_size_valid, final_image_size = self._validate_image_size(image_size)
        log_info(
            f"生图尺寸：{final_image_size}（请求尺寸：{image_size or '默认'}，{'有效' if is_size_valid else '无效，已自动调整'}）")

        # 4. 调用检索模块获取参考信息
        retrieval_info = self._get_retrieval_info(prompt, style)

        # 5. 构建提示词（无固定尺寸限制）
        full_prompt = self.config.prompt_template.format(
            prompt=prompt,
            style=style,
            retrieval_info=retrieval_info
        ).strip()
        log_info(f"生图请求：模型={self.model['name']}，主题={prompt}，风格={style}，提示词={full_prompt[:80]}...")

        # 6. 构造请求参数
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.model['api_key']}"
        }
        request_data = {}

        if self.model["request_format"] == "volc":
            request_data = {
                "model": self.model["model_id"],
                "prompt": full_prompt,
                "sequential_image_generation": "disabled",
                "response_format": "url",
                "size": final_image_size,  # 使用校验后的有效尺寸
                "stream": False,
                "watermark": True
            }
        elif self.model["request_format"] == "aliyun":
            request_data = {
                "model": self.model["model_id"],
                "input": {"prompt": full_prompt},
                "parameters": {
                    "size": final_image_size,
                    "response_format": "url",
                    "quality": "high"
                }
            }

        # 7. 带重试的API调用
        start_time = time.time()
        for retry in range(self.model["max_retries"] + 1):
            try:
                response = requests.post(
                    url=self.model["api_url"],
                    headers=headers,
                    json=request_data,
                    timeout=self.model["timeout"]
                )
                response.raise_for_status()
                response_data = response.json()
                generate_time = round(time.time() - start_time, 2)

                # 解析图片URL
                if self.model["request_format"] == "volc":
                    image_url = response_data["data"][0]["url"]
                elif self.model["request_format"] == "aliyun":
                    image_url = response_data["output"]["url"]
                else:
                    image_url = ""

                log_info(f"生图成功：耗时={generate_time}秒，图片URL={image_url[:50]}...")

                local_path = save_image_local(image_url, prompt, self.model["name"], config.local_save_dir)
                log_info(f"图片已保存到：{local_path}")

                return local_path

            except requests.exceptions.RequestException as e:
                error_detail = str(e)
                if hasattr(e, "response") and e.response is not None:
                    error_detail += f" | 状态码：{e.response.status_code} | 响应：{e.response.text[:100]}"
                if retry < self.model["max_retries"]:
                    log_error(f"生图失败（重试{retry + 1}/{self.model['max_retries']}）：{error_detail[:80]}")
                    time.sleep(3)
                else:
                    error_msg = f"生图失败（已重试{self.model['max_retries']}次）：{error_detail[:100]}"
                    log_error(error_msg)
                    return ""
            except Exception as e:
                error_msg = f"生图系统错误：{str(e)[:100]}"
                log_error(error_msg)
                return ""

    def batch_generate(self, tasks: List[Dict]) -> List[str]:
        """批量生图接口（修复任务显示问题）"""
        # 过滤空任务，避免无效请求
        tasks = [task for task in tasks if task.get("prompt") and task.get("style")]
        if not tasks:
            log_info("批量生图：无有效任务（主题或风格为空）")
            return []


        log_info(f"开始批量生图，共{len(tasks)}个有效任务")
        batch_results = []
        for idx, task in enumerate(tasks, 1):
            prompt = task.get("prompt", "").strip()
            style = task.get("style", "").strip()
            model_key = task.get("model_key", None)
            image_size = task.get("image_size", None)
            log_info(f"\n批量任务{idx}/{len(tasks)}：主题={prompt}，风格={style}，尺寸={image_size or '默认1024x1024'}")
            result = self.generate_image(prompt, style, model_key, image_size)
            batch_results.append(result)

        log_info(f"批量生图完成，共{len(batch_results)}个结果")
        return batch_results


# ===================== 检索模块对接示例（不变）=====================
def mock_rag_retrieval(prompt: str, style: str) -> str:
    mock_data = {
        "元宵节花灯": "元宵节花灯文化：传统花灯多以红灯笼为基础，搭配龙、凤、牡丹等吉祥图案，色彩以红、金为主，象征团圆喜庆，常见造型有宫灯、走马灯等。",
        "端午节龙舟": "龙舟文化特点：传统龙舟船体修长，头部雕刻龙形，色彩鲜艳（红、黄、蓝为主），龙舟上插彩旗，体现端午节驱邪避灾、祈福安康的文化内涵。",
        "中秋节玉兔": "中秋玉兔元素：玉兔是中秋节核心象征之一，传统形象为白色玉兔持捣药杵，背景常搭配月亮、桂树，风格多温婉、静谧，色彩以白、黄、银为主。"
    }
    return mock_data.get(prompt, f"未检索到{prompt}的相关参考信息")


# ===================== 功能测试与使用示例 =====================
if __name__ == "__main__":
    # 初始化AIGC功能（默认1024x1024尺寸）
    try:
        aigc = ImageAIGC()

        # 示例1：单张生图（默认1024x1024，模型支持，成功率100%）
        log_info("\n=== 测试：默认1024x1024尺寸，单张生图 ===")
        local_path = aigc.generate_image(
            prompt="中秋节玉兔",
            style="现代简约风"
        )
        if local_path:
            print(f"\n图片已保存到本地：{local_path}")
        else:
            print("\n图片生成失败")

        # 示例2：批量生图（包含无效尺寸测试，自动调整为支持的尺寸）
        log_info("\n=== 测试：批量生图（支持自动调整无效尺寸）===")
        batch_tasks = [
            {"prompt": "中秋节玉兔", "style": "现代简约风"},  # 默认1024x1024（有效）
            {"prompt": "重阳节菊花", "style": "古典工笔风", "image_size": "512x512"},  # 无效尺寸，自动调整
            {"prompt": "春节春联", "style": "喜庆红黑风"},  # 默认1024x1024（有效）
            {"prompt": "元宵节花灯", "style": "传统红金风", "image_size": "2048x2048"}  # 支持的尺寸
        ]
        batch_results = aigc.batch_generate(batch_tasks)
        print("\n批量生图结果汇总：")
        for idx, local_path in enumerate(batch_results):
            task = batch_tasks[idx]
            print(
                f"任务{idx+1} - 主题：{task['prompt']} → 风格：{task['style']} → "
                f"保存路径：{local_path if local_path else '失败'}"
            )
    except ValueError as e:
        log_error(f"初始化失败：{str(e)}")
        
    except Exception as e:
        log_error(f"运行出错：{str(e)}")




