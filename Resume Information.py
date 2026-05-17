import os
import base64
import json
import time
import logging
import pandas as pd
from openai import OpenAI
from collections import deque, defaultdict
from tenacity import retry, stop_after_attempt, wait_exponential
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock, current_thread
import traceback

# ==================== 配置区域 ====================
# 在此处添加您的多个API密钥（至少2个）
MOONSHOT_API_KEYS = [
    "sk-lubwLnYZlPQxogQjPN1y1GeHfP3Zc63Q5X7PwiyJhHe1MZ6Y",
    "sk-ZwuXZO4oAFDvOy7zYReuvi5tyjc4apt36VRlmM6fmu9upPrK",
    "sk-22Q05Gw8TAkJKlaNJldPovHZaFjv0hejwUN6VMynW6T82thG",
    "sk-l8ha7CTke1Tckm0HCIC8EiCBwLswUcIlACT5thf773jrEd0Z",
    "sk-cA114BkOA5Krq0KafGa2A4GDFXV0ojcW4zlBqwrvweBSg0bO",
    "sk-ELxMzGYTU2SmjKTalQs8InSYcfVp7QfGHF9VXEyJhKi1ufOS",
    "sk-hxx2QJa5teRo65pHuNsEoZ9CYp3WYJbteczKC71xMK6GYTcC",
    "sk-EjDaC4SGns5vJNCtw2GYJ50UNB8K9entfFxRiDrnAJlc71zh",
    "sk-kzQKYgCIsBsSyLvSUfFQ5k6h44jc5GPjFk6DQLBtH0tKrjdv",
]

# API限制配置（根据Moonshot实际限制调整）
RATE_LIMIT_PER_KEY = {
    'TPM': 32000,  # 每分钟tokens
    'RPM': 3,  # 每分钟请求数（每个密钥）
    'TPD': 1500000  # 每天tokens
}

# 并发处理配置
MAX_WORKERS = len(MOONSHOT_API_KEYS)  # 最大并发数等于密钥数量
REQUEST_INTERVAL = 60 / RATE_LIMIT_PER_KEY['RPM']  # 每个密钥的最小请求间隔

# 文件路径配置
RESUME_FOLDER = "D:/简历图片提取"  # 简历文件夹路径
OUTPUT_FILE = "resume_results.csv"  # 输出文件名（CSV格式）

# 日志级别配置
LOG_LEVEL = logging.INFO  # 可设置为 DEBUG/INFO/WARNING/ERROR


# ==================================================

# ==================== 日志配置 ====================
class ThreadNameFilter(logging.Filter):
    """添加线程名称到日志记录的过滤器"""

    def filter(self, record):
        record.threadname = current_thread().name
        return True


def setup_logging():
    """配置详细的日志记录系统"""
    logger = logging.getLogger()
    logger.setLevel(LOG_LEVEL)

    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(LOG_LEVEL)

    # 创建文件处理器
    file_handler = logging.FileHandler('resume_processor.log', encoding='utf-8')
    file_handler.setLevel(LOG_LEVEL)

    # 创建日志格式
    formatter = logging.Formatter(
        '%(asctime)s | %(threadname)-15s | %(levelname)-8s | %(message)s'
    )

    # 添加线程名称过滤器
    thread_filter = ThreadNameFilter()

    # 配置处理器
    for handler in [console_handler, file_handler]:
        handler.setFormatter(formatter)
        handler.addFilter(thread_filter)
        logger.addHandler(handler)

    logger.info("=" * 80)
    logger.info("简历处理程序启动 - 日志系统初始化完成")
    logger.info(f"日志级别设置为: {logging.getLevelName(LOG_LEVEL)}")
    logger.info("=" * 80)


setup_logging()
logger = logging.getLogger(__name__)


# ==================================================

class APIKeyRotator:
    """多API密钥轮转管理器（优化版）"""

    def __init__(self, api_keys, rate_limits):
        self.available_keys = deque(api_keys)
        self.key_usage_stats = defaultdict(dict)
        self.rate_limits = rate_limits
        self.lock = Lock()

        # 初始化所有密钥的状态跟踪
        now = time.time()
        for key in api_keys:
            self.key_usage_stats[key] = {
                'last_used': 0,
                'requests_today': 0,
                'tokens_today': 0,
                'tpm_used': 0,
                'tpm_reset_time': now + 60,
                'daily_reset_time': now + 86400,
                'consecutive_errors': 0,
                'next_available_time': 0  # 下次可用时间
            }

        logger.info(f"API密钥轮转管理器初始化完成 - 已加载 {len(api_keys)} 个API密钥")
        logger.debug(f"API密钥列表: {[k[:6] + '...' + k[-4:] for k in api_keys]}")
        logger.info(f"最大并发数: {MAX_WORKERS} | 每个密钥最小请求间隔: {REQUEST_INTERVAL:.2f}秒")

    def get_available_key(self):
        """获取当前可用的API密钥，考虑所有限制"""
        with self.lock:
            now = time.time()
            best_key = None
            min_wait_time = float('inf')

            # 寻找最快可用的密钥
            for key in self.available_keys:
                stats = self.key_usage_stats[key]

                # 重置每日配额（如果过了一天）
                if now > stats['daily_reset_time']:
                    old_stats = stats.copy()
                    stats.update({
                        'requests_today': 0,
                        'tokens_today': 0,
                        'daily_reset_time': now + 86400,
                        'consecutive_errors': 0
                    })
                    logger.info(f"密钥 {key[-6:]}... 每日配额已重置 - "
                                f"旧状态: 请求 {old_stats['requests_today']}次, "
                                f"Tokens {old_stats['tokens_today']}")

                # 重置每分钟配额（如果过了一分钟）
                if now > stats['tpm_reset_time']:
                    old_tpm = stats['tpm_used']
                    stats.update({
                        'tpm_used': 0,
                        'tpm_reset_time': now + 60
                    })
                    logger.debug(f"密钥 {key[-6:]}... 分钟配额已重置 - 已用Tokens: {old_tpm}")

                # 检查是否达到任何限制
                if (stats['tokens_today'] >= self.rate_limits['TPD'] or
                        stats['tpm_used'] >= self.rate_limits['TPM'] or
                        stats['consecutive_errors'] >= 3):
                    logger.debug(f"密钥 {key[-6:]}... 当前不可用 - "
                                 f"今日Tokens: {stats['tokens_today']}/{self.rate_limits['TPD']}, "
                                 f"当前分钟Tokens: {stats['tpm_used']}/{self.rate_limits['TPM']}, "
                                 f"连续错误: {stats['consecutive_errors']}")
                    continue

                # 计算需要等待的时间
                wait_time = max(0, stats['next_available_time'] - now)
                logger.debug(f"密钥 {key[-6:]}... 可用性检查 - 需要等待: {wait_time:.2f}秒")

                # 选择等待时间最短的密钥
                if wait_time < min_wait_time:
                    min_wait_time = wait_time
                    best_key = key

            if best_key:
                # 更新密钥的下次可用时间
                self.key_usage_stats[best_key]['next_available_time'] = now + min_wait_time + REQUEST_INTERVAL

                # 如果需要等待，则休眠
                if min_wait_time > 0:
                    logger.debug(f"等待 {min_wait_time:.2f} 秒后使用密钥 {best_key[-6:]}...")
                    time.sleep(min_wait_time)

                logger.info(f"选择密钥 {best_key[-6:]}... 进行请求")
                return best_key

            # 所有密钥都达到限制时的处理
            self.log_key_status()
            raise RuntimeError("所有API密钥都已达到限制，请稍后再试")

    def update_key_stats(self, key, tokens_used=0, error_occurred=False):
        """更新密钥使用统计"""
        with self.lock:
            stats = self.key_usage_stats[key]
            now = time.time()

            stats['last_used'] = now
            if error_occurred:
                stats['consecutive_errors'] += 1
                logger.warning(f"密钥 {key[-6:]}... 发生错误（连续 {stats['consecutive_errors']} 次）")
            else:
                stats['consecutive_errors'] = 0
                stats['requests_today'] += 1
                stats['tokens_today'] += tokens_used
                stats['tpm_used'] += tokens_used
                logger.info(f"密钥 {key[-6:]}... 使用更新 - "
                            f"今日请求: {stats['requests_today']}次, "
                            f"今日Tokens: {stats['tokens_today']}/{self.rate_limits['TPD']}, "
                            f"当前分钟Tokens: {stats['tpm_used']}/{self.rate_limits['TPM']}")

    def log_key_status(self):
        """记录所有密钥的当前状态"""
        logger.warning("=" * 50 + " API密钥状态报告 " + "=" * 50)
        for key, stats in self.key_usage_stats.items():
            status = []
            if stats['tokens_today'] >= self.rate_limits['TPD']:
                status.append("已达每日限额")
            if stats['tpm_used'] >= self.rate_limits['TPM']:
                status.append("已达每分钟限额")
            if stats['consecutive_errors'] >= 3:
                status.append(f"连续错误{stats['consecutive_errors']}次")

            status_str = " | ".join(status) if status else "可用"

            logger.warning(
                f"密钥 {key[-6:]}...: {status_str:<20} | "
                f"今日已用: {stats['tokens_today']:>7}/{self.rate_limits['TPD']:<7} tokens | "
                f"当前分钟: {stats['tpm_used']:>5}/{self.rate_limits['TPM']:<5} tokens | "
                f"最后使用: {time.strftime('%H:%M:%S', time.localtime(stats['last_used']))}"
            )
        logger.warning("=" * 120)


# ==================== 文件操作 ====================
def init_output_file():
    """初始化输出文件（如果不存在）"""
    try:
        if not os.path.exists(OUTPUT_FILE):
            with open(OUTPUT_FILE, mode='w', encoding='utf-8-sig') as f:
                columns = [
                    "文件名", "姓名", "性别", "出生年月",
                    "手机号码", "最高学历", "毕业学校", "毕业年份",
                    "地区", "专业名称", "应聘职位"
                ]
                pd.DataFrame(columns=columns).to_csv(f, index=False)
            logger.info(f"已创建新的输出文件: {OUTPUT_FILE}")
        else:
            existing_count = len(pd.read_csv(OUTPUT_FILE))
            logger.info(f"检测到现有输出文件: {OUTPUT_FILE} - 已有 {existing_count} 条记录")
    except Exception as e:
        logger.error(f"初始化输出文件失败: {str(e)}\n{traceback.format_exc()}")
        raise


def append_resume_data(data):
    """追加单条简历数据到CSV（线程安全版）"""
    lock = Lock()
    try:
        with lock:
            # 检查是否已存在相同文件名的记录
            if os.path.exists(OUTPUT_FILE):
                existing = pd.read_csv(OUTPUT_FILE)
                if data["文件名"] in existing["文件名"].values:
                    logger.warning(f"跳过已存在的记录: {data['文件名']}")
                    return False

            # 追加新记录
            with open(OUTPUT_FILE, mode='a', encoding='utf-8-sig', newline='') as f:
                pd.DataFrame([data]).to_csv(f, header=f.tell() == 0, index=False)

            logger.debug(f"成功写入记录: {data['文件名']}")
            return True
    except Exception as e:
        logger.error(f"写入CSV失败: {str(e)}\n数据: {data}\n{traceback.format_exc()}")
        return False


# ==================== 核心功能 ====================
def image_to_base64(image_path):
    """将图片转换为base64编码"""
    try:
        with open(image_path, "rb") as image_file:
            result = base64.b64encode(image_file.read()).decode('utf-8')
            logger.debug(f"成功将图片转换为Base64: {os.path.basename(image_path)}")
            return result
    except Exception as e:
        logger.error(f"图片转换失败: {image_path} | 错误: {str(e)}\n{traceback.format_exc()}")
        raise


def extract_resume_info_with_retry(image_path, key_rotator, max_retries=3):
    """带Key轮换的重试机制"""
    last_error = None
    for attempt in range(max_retries):
        current_key = None
        try:
            current_key = key_rotator.get_available_key()
            logger.info(f"开始处理(尝试 {attempt + 1}/{max_retries}): {os.path.basename(image_path)} | "
                        f"使用密钥: {current_key[-6:]}...")

            base64_image = image_to_base64(image_path)
            client = OpenAI(api_key=current_key, base_url="https://api.moonshot.cn/v1")

            start_time = time.time()
            logger.debug(f"发送API请求: {os.path.basename(image_path)}")

            response = client.chat.completions.create(
                model="moonshot-v1-8k-vision-preview",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "你是一个专业的简历信息提取系统。请严格按以下要求及格式从简历中提取信息并以JSON格式返回:\n"
                            "1. 姓名\n2. 性别(男/女)\n3. 出生年月(YYYY-MM)\n4. 手机号码(11位)\n"
                            "5. 最高学历(大专/本科/硕士/博士)\n6. 毕业学校\n7. 毕业年份(YYYY)\n8. 地区(省/市)\n9. 专业名称\n10. 应聘职位\n"
                            "示例: {'姓名':'张三','性别':'男','出生年月':'1990-05','手机号码'：‘11111111111’...}\n"
                            "只返回JSON数据，不要任何解释！"
                        )
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}},
                            {"type": "text", "text": "请从这份简历中提取上述要求的个人信息。"}
                        ]
                    }
                ],
                temperature=0.1
            )

            processing_time = time.time() - start_time
            tokens_used = response.usage.total_tokens
            logger.info(f"处理成功: {os.path.basename(image_path)} | "
                        f"用时: {processing_time:.2f}s | Tokens: {tokens_used}")

            info = json.loads(response.choices[0].message.content)
            key_rotator.update_key_stats(current_key, tokens_used)
            return info, tokens_used

        except Exception as e:
            last_error = e
            logger.error(f"处理失败(尝试 {attempt + 1}/{max_retries}): {os.path.basename(image_path)} | "
                         f"错误类型: {type(e).__name__} | 错误详情: {str(e)}")
            if current_key:
                key_rotator.update_key_stats(current_key, error_occurred=True)

            # 如果不是最后一次尝试，则等待一段时间再重试
            if attempt < max_retries - 1:
                wait_time = min(5 * (attempt + 1), 30)  # 指数退避，最多等待30秒
                logger.info(f"等待 {wait_time} 秒后重试...")
                time.sleep(wait_time)

    logger.error(f"所有尝试失败: {os.path.basename(image_path)} | 最后错误: {str(last_error)}")
    raise last_error if last_error else Exception("未知错误")


def process_single_resume(filename, key_rotator):
    """处理单个简历文件"""
    image_path = os.path.join(RESUME_FOLDER, filename)

    try:
        logger.info(f"开始处理简历文件: {filename}")

        # 提取简历信息（带自动重试和Key轮换）
        info, tokens_used = extract_resume_info_with_retry(image_path, key_rotator)

        if info:
            # 构造数据记录
            record = {
                "文件名": filename,
                "姓名": info.get("姓名", ""),
                "性别": info.get("性别", ""),
                "出生年月": info.get("出生年月", ""),
                "手机号码": info.get("手机号码", ""),
                "最高学历": info.get("最高学历", ""),
                "毕业学校": info.get("毕业学校", ""),
                "毕业年份": info.get("毕业年份", ""),
                "地区": info.get("地区", ""),
                "专业名称": info.get("专业名称", ""),
                "应聘职位": info.get("应聘职位", ""),
            }

            logger.debug(f"提取的信息: {json.dumps(record, indent=2, ensure_ascii=False)}")

            # 立即写入CSV
            if append_resume_data(record):
                logger.info(f"成功保存: {filename} | 姓名: {record['姓名']}")
                return True
            else:
                logger.warning(f"跳过重复记录: {filename}")
                return False

    except Exception as e:
        logger.error(f"最终处理失败: {filename} | 错误: {str(e)}\n{traceback.format_exc()}")
        return False


def process_resumes():
    """主处理流程（并行版）"""
    logger.info("=" * 80)
    logger.info("简历处理程序启动")
    logger.info("=" * 80)

    init_output_file()
    key_rotator = APIKeyRotator(MOONSHOT_API_KEYS, RATE_LIMIT_PER_KEY)

    # 获取所有待处理简历文件
    try:
        resume_files = [
            f for f in os.listdir(RESUME_FOLDER)
            if f.lower().endswith(('.png', '.jpg', '.jpeg', '.pdf'))
        ]

        if not resume_files:
            logger.error("未找到任何简历文件！")
            return

        logger.info(f"发现 {len(resume_files)} 份待处理简历")
        logger.debug(f"文件列表: {resume_files[:5]}{'...' if len(resume_files) > 5 else ''}")
    except Exception as e:
        logger.error(f"读取简历文件夹失败: {str(e)}\n{traceback.format_exc()}")
        return

    processed_count = 0
    failed_count = 0

    # 使用线程池并行处理
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(process_single_resume, filename, key_rotator): filename
            for filename in resume_files
        }

        for future in as_completed(futures):
            if future.result():
                processed_count += 1
            else:
                failed_count += 1

            # 定期报告进度
            if (processed_count + failed_count) % 10 == 0:
                logger.info(f"处理进度: 已处理 {processed_count + failed_count}/{len(resume_files)} | "
                            f"成功: {processed_count} | 失败: {failed_count}")

    logger.info("=" * 80)
    logger.info(f"处理完成！总计: {len(resume_files)} 份简历")
    logger.info(f"成功处理: {processed_count} 份 | 处理失败: {failed_count} 份")
    logger.info("=" * 80)


if __name__ == "__main__":
    try:
        process_resumes()
    except Exception as e:
        logger.critical(f"程序运行出错: {str(e)}\n{traceback.format_exc()}")
    finally:
        logger.info("程序执行结束")