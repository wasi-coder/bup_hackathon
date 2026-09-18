"""Warm both model weights and the shared system-prompt prefix before serving."""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
from gridwise.llm import PROMPT, Settings
from gridwise.models import Interpretation


async def main():
    settings = Settings.from_env()
    async with httpx.AsyncClient(timeout=120, trust_env=False) as client:
        response = await client.post(settings.base_url + '/api/chat', json={
            'model': settings.model, 'stream': False, 'keep_alive': '30m',
            'format': Interpretation.model_json_schema(),
            'messages': [{'role': 'system', 'content': PROMPT}, {'role': 'user', 'content': json.dumps({
                'operator_notes': ['The lunch menu changes next week.'], 'battery_capacity_kwh': 200})}],
            'options': settings.generation_options(),
        })
        response.raise_for_status()
        Interpretation.model_validate_json(response.json()['message']['content'])
        print('Local model and shared prompt are warm.')


if __name__ == '__main__':
    asyncio.run(main())
