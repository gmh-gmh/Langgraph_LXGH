from backend.utils.config_handler import prompts_config
from backend.utils.logger_handler import logger
from backend.utils.path_tool import get_abs_path

def load_eval_prompts():
    try:
        eval_prompt_path = get_abs_path(prompts_config["eval_prompt_path"])
    except KeyError as e:
        logger.error(f"[load_report_prompts]在yaml配置项中没有eval_prompt_path配置项")
        raise e

    try:
        return open(eval_prompt_path, "r", encoding="utf-8").read()
    except Exception as e:
        logger.error(f"[load_eval_prompts]解析报告生成提示词出错，{str(e)}")
        raise e

def load_image_prompts():
    try:
        image_prompt_path = get_abs_path(prompts_config["image_prompt_path"])
    except KeyError as e:
        logger.error(f"[load_image_prompts]在yaml配置项中没有image_prompt_path配置项")
        raise e

    try:
        return open(image_prompt_path, "r", encoding="utf-8").read()
    except Exception as e:
        logger.error(f"[load_image_prompts]解析报告生成提示词出错，{str(e)}")
        raise e

def load_intent_prompts():
    try:
        intent_prompt_path = get_abs_path(prompts_config["intent_prompt_path"])
    except KeyError as e:
        logger.error(f"[load_intent_prompts]在yaml配置项中没有intent_prompt_path配置项")
        raise e

    try:
        return open(intent_prompt_path, "r", encoding="utf-8").read()
    except Exception as e:
        logger.error(f"[load_intent_prompts]解析报告生成提示词出错，{str(e)}")
        raise e

def load_rewrite_prompts():
    try:
        rewrite_prompt_path = get_abs_path(prompts_config["rewrite_prompt_path"])
    except KeyError as e:
        logger.error(f"[load_rewrite_prompts]在yaml配置项中没有rewrite_prompt_path配置项")
        raise e

    try:
        return open(rewrite_prompt_path, "r", encoding="utf-8").read()
    except Exception as e:
        logger.error(f"[load_rewrite_prompts]解析改写提示词出错，{str(e)}")
        raise e