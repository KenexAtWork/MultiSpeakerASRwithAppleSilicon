"""
Summary Worker - 透過 AWS Bedrock 產生會議摘要
支援 Claude (Anthropic) 和 Amazon Nova 模型
使用 Bedrock Converse API 統一呼叫格式
"""
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

格式處理
- 中英文及數字之間(中文 --> 英文、英文 -> 中文、中文 -> 數字.. ) ，需要補上空格，方便文字閱讀
- 所有輸出均為 "正體中文"

---

會議轉錄內容：
{transcript}"""


class SummaryWorker(QThread):
    """Bedrock 摘要 Worker（Converse API，支援 Claude + Nova）"""

    progress = pyqtSignal(str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

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

            self.progress.emit("⏳ 等待 LLM 回應...")

            # 使用 Converse API — 統一支援 Claude / Nova / 其他模型
            response = client.converse(
                modelId=self.model_id,
                messages=[
                    {"role": "user", "content": [{"text": prompt}]}
                ],
                inferenceConfig={"maxTokens": 4096}
            )

            # Converse API 統一回傳格式
            output = response["output"]["message"]["content"]
            summary = "".join(block["text"] for block in output if "text" in block)

            self.progress.emit("✓ 摘要產生完成")
            self.finished.emit(summary)

        except Exception as e:
            self.error.emit(str(e))
