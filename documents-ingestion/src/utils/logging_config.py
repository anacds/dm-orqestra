import logging
import sys
from datetime import datetime


class CleanFormatter(logging.Formatter):
    LEVEL_COLORS = {
        "DEBUG": "\033[36m",      # cyan
        "INFO": "\033[32m",       # green
        "WARNING": "\033[33m",    # yellow
        "ERROR": "\033[31m",      # red
        "CRITICAL": "\033[35m",   # magenta
    }
    RESET = "\033[0m"

    def format(self, record):
        timestamp = datetime.now().strftime("%H:%M:%S")
        level = record.levelname
        
        color = self.LEVEL_COLORS.get(level, "")
        reset = self.RESET if color else ""
        
        logger_name = record.name.replace("src.", "").replace("__main__", "pipeline")
        
        message = record.getMessage()
        
        if record.exc_info:
            message += f"\n{self.formatException(record.exc_info)}"
        
        return f"{timestamp} {color}[{level:8}]{reset} {logger_name:20} | {message}"


def setup_logging(level: str = "INFO", structured: bool = False):
    log_level = getattr(logging, level.upper(), logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)

    if structured:
        import json
        from datetime import datetime
        
        class StructuredFormatter(logging.Formatter):
            def format(self, record):
                log_data = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "level": record.levelname,
                    "logger": record.name,
                    "message": record.getMessage(),
                }
                if hasattr(record, "extra"):
                    log_data.update(record.extra)
                if record.exc_info:
                    log_data["exception"] = self.formatException(record.exc_info)
                return json.dumps(log_data, ensure_ascii=False)
        
        formatter = StructuredFormatter()
    else:
        formatter = CleanFormatter()

    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
    
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

