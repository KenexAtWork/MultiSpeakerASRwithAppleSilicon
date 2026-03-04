"""
Live Summary Worker - Periodically summarizes accumulated realtime ASR text
using AWS Bedrock (Claude / Nova).

Trigger: every N transcript segments or T seconds, whichever comes first.
Incremental: sends previous summary + new text to LLM for updated notes.
"""
import boto3
from PyQt6.QtCore import QThread, pyqtSignal

DEFAULT_LIVE_PROMPT = """\
You are a real-time meeting note-taker. Given the previous summary (if any) and new transcript segments, produce an updated structured summary.

Rules:
- Output in the SAME language as the transcript (if Chinese, use Traditional Chinese 正體中文)
- Add spacing between Chinese and English/numbers for readability
- Be concise — bullet points, not paragraphs
- Preserve important details from the previous summary
- Merge and deduplicate overlapping content

Format:
## 重點摘要 / Key Points
- (bullet points of main topics discussed)

## 待辦事項 / Action Items
- (if any mentioned)

## 備註 / Notes
- (any other notable details)

---

Previous summary:
{previous_summary}

New transcript segments:
{new_text}

Updated summary:"""


class LiveSummaryWorker(QThread):
    """Sends accumulated transcript to Bedrock for incremental summarization."""

    summary_updated = pyqtSignal(str)   # full updated summary text
    status = pyqtSignal(str)            # status messages
    error = pyqtSignal(str)

    def __init__(self, new_texts: list[str], previous_summary: str = "",
                 model_id: str = "apac.anthropic.claude-3-5-sonnet-20241022-v2:0",
                 region: str | None = None,
                 prompt_template: str | None = None):
        super().__init__()
        self.new_texts = new_texts
        self.previous_summary = previous_summary
        self.model_id = model_id
        self.region = region
        self.prompt_template = prompt_template or DEFAULT_LIVE_PROMPT

    def run(self):
        try:
            new_text = "\n".join(self.new_texts)
            if not new_text.strip():
                return

            self.status.emit("📝 Generating summary...")

            session = boto3.Session()
            region = self.region or session.region_name or "us-east-1"
            client = session.client("bedrock-runtime", region_name=region)

            prompt = self.prompt_template.replace(
                "{previous_summary}", self.previous_summary or "(none)"
            ).replace(
                "{new_text}", new_text
            )

            response = client.converse(
                modelId=self.model_id,
                messages=[
                    {"role": "user", "content": [{"text": prompt}]}
                ],
                inferenceConfig={"maxTokens": 2048}
            )

            output = response["output"]["message"]["content"]
            summary = "".join(block["text"] for block in output if "text" in block)

            self.summary_updated.emit(summary.strip())
            self.status.emit("✅ Summary updated")

        except Exception as e:
            self.error.emit(f"Summary error: {e}")
