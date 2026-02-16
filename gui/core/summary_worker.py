"""
Summary Worker - 透過 AWS Bedrock (Claude) 產生會議摘要
"""
import json
import boto3
from PyQt6.QtCore import QThread, pyqtSignal


DEFAULT_PROMPT = """你是一位專業的會議記錄整理助手。請根據以下會議轉錄內容，產生結構化的會議摘要。

請包含以下部分：

## 會議重點
- 條列式整理會議中討論的主要議題和結論

## Action Items（待辦事項）
- 列出會議中提到的待辦事項，標註負責人（如果有提到）

## 各說話者發言重點
- 按說話者分別整理其主要發言內容和觀點

## 會議結論
- 簡要總結會議的最終決議或共識

---

會議轉錄內容：
{transcript}"""


class SummaryWorker(QThread):
    """Bedrock Claude 摘要 Worker"""

    progress = pyqtSignal(str)   # 進度訊息
    finished = pyqtSignal(str)   # 完成（摘要內容）
    error = pyqtSignal(str)      # 錯誤

    def __init__(self, transcript, prompt_template=None,
                 model_id="apac.anthropic.claude-3-5-sonnet-20241022-v2:0",
                 region=None):
        super().__init__()
        self.transcript = transcript
        self.prompt_template = prompt_template or DEFAULT_PROMPT
        self.model_id = model_id
        self.region = region

    def run(self):
        try:
            self.progress.emit("⏳ 連線 AWS Bedrock...")

            session = boto3.Session()
            region = self.region or session.region_name or "us-east-1"
            client = session.client("bedrock-runtime", region_name=region)

            self.progress.emit(f"⏳ 使用模型: {self.model_id} ({region})")

            prompt = self.prompt_template.replace("{transcript}", self.transcript)

            body = json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 4096,
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            })

            self.progress.emit("⏳ 等待 LLM 回應...")

            response = client.invoke_model(
                modelId=self.model_id,
                contentType="application/json",
                accept="application/json",
                body=body
            )

            result = json.loads(response["body"].read())
            summary = result["content"][0]["text"]

            self.progress.emit("✓ 摘要產生完成")
            self.finished.emit(summary)

        except Exception as e:
            self.error.emit(str(e))
