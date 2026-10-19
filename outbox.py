"""B 방식용 영속 대기열(Supabase) 및 Google Sheets 1분 동기화.

Streamlit Community Cloud의 임시 디스크/메모리를 대기열로 사용하지 않는다.
"""
from __future__ import annotations

import uuid
from typing import Any
import requests

from gauge_core import build_outbox_transaction


class QueueError(RuntimeError):
    pass


class SupabaseOutbox:
    def __init__(self, url: str, service_key: str):
        self.endpoint = url.rstrip('/') + '/rest/v1/gauge_outbox'
        self.headers = {
            'apikey': service_key,
            'Authorization': f'Bearer {service_key}',
            'Content-Type': 'application/json',
        }

    def _request(self, method: str, **kwargs):
        try:
            headers = {**self.headers, **kwargs.pop('headers', {})}
            response = requests.request(method, self.endpoint, headers=headers, timeout=12, **kwargs)
            response.raise_for_status()
            return response.json() if response.content else None
        except (requests.RequestException, ValueError) as exc:
            raise QueueError(f'대기열 연결 실패: {exc}') from exc

    def add(self, changes: list[dict], *, event_id: str | None = None) -> str:
        if not changes:
            raise ValueError('빈 작업은 저장할 수 없습니다.')
        event_id = event_id or str(uuid.uuid4())
        self._request('POST', params={'on_conflict': 'id'}, json={'id': event_id, 'changes': changes},
                      headers={**self.headers, 'Prefer': 'return=minimal,resolution=ignore-duplicates'})
        return event_id

    def pending(self) -> list[dict]:
        result = self._request('GET', params={
            'select': 'id,sequence_id,changes', 'state': 'eq.pending',
            'order': 'sequence_id.asc', 'limit': '500',
        })
        return result or []

    def delivered(self, ids: list[str]) -> None:
        if not ids:
            return
        self._request('PATCH', params={'id': f'in.({",".join(ids)})', 'state': 'eq.pending'},
                      json={'state': 'delivered'},
                      headers={**self.headers, 'Prefer': 'return=minimal'})


def marker(event_id: str, index: int) -> str:
    return f'{event_id}:{index}'


def apply_pending(rows: list[dict], events: list[dict]) -> list[dict]:
    """Supabase에 안전히 기록된 미전송 이벤트를 태블릿 화면에 먼저 반영."""
    from gauge_core import update_local_records
    changes = [change for event in events for change in event['changes']]
    return update_local_records(rows, changes)


def flush_events(outbox: SupabaseOutbox, spreadsheet: Any, status_sheet: Any, logs_sheet: Any) -> int:
    """1회 batchUpdate, 로그의 UUID 표식을 확인하여 응답 손실 뒤 재실행도 중복 방지.

    Google Sheets Logs의 E열은 내부 동기화 식별자에만 사용한다.
    """
    events = outbox.pending()
    if not events:
        return 0
    # 이전 시도에서 Sheets 반영은 성공했지만 Supabase 완료 표시만 실패했을 수 있다.
    already = set(logs_sheet.col_values(5))
    all_markers = []
    missing_changes = []
    for event in events:
        for index, change in enumerate(event['changes']):
            record_id = marker(event['id'], index)
            all_markers.append(record_id)
            if record_id not in already:
                missing_changes.append({**change, '로그ID': record_id})
    if missing_changes:
        payload = build_outbox_transaction(missing_changes, status_sheet.id, logs_sheet.id)
        spreadsheet.batch_update(payload)
    # 로그가 정상 기록됐으면 그때만 Supabase 대기 상태 해제
    outbox.delivered([event['id'] for event in events])
    return len(missing_changes)
