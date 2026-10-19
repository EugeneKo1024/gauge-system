"""게이지 현황 파싱 및 Google Sheets 단일 요청 생성 (Streamlit 비의존)."""
from __future__ import annotations

from typing import Iterable

EXPECTED_HEADERS = ("게이지명", "상태", "대여자", "대여일시")


def parse_status_table(values: list[list[str]]) -> list[dict]:
    """Status 시트의 실제 행 번호를 보존한다. 중간 빈 행이 있어도 안전하다."""
    if not values:
        raise ValueError("Status 시트가 비어 있습니다.")
    header = [str(value).strip() for value in values[0][:4]]
    if header != list(EXPECTED_HEADERS):
        raise ValueError(
            "Status 시트 A~D열 제목이 예상과 다릅니다. "
            "게이지명 / 상태 / 대여자 / 대여일시 순서를 확인하세요."
        )
    records: list[dict] = []
    names: set[str] = set()
    for index, row in enumerate(values[1:], start=2):
        data = list(row[:4]) + [""] * max(0, 4 - len(row))
        name = str(data[0]).strip()
        if not name:
            continue
        if name in names:
            raise ValueError(f"Status 시트에서 중복 게이지명 발견: {name}")
        names.add(name)
        records.append(
            {
                "sheet_row": index,
                "게이지명": name,
                "상태": str(data[1]).strip(),
                "대여자": str(data[2]).strip(),
                "대여일시": str(data[3]).strip(),
            }
        )
    return records


def _text_cell(value: str) -> dict:
    """값이 '=SUM(...)' 형태여도 수식으로 실행되지 않는 문자열 셀."""
    return {"userEnteredValue": {"stringValue": str(value)}}


def build_transaction(
    changes: Iterable[dict], status_sheet_id: int, logs_sheet_id: int
) -> dict:
    """여러 게이지 상태 변경 + 모든 이력 추가를 한 batchUpdate 호출로 묶는다.

    각 change: sheet_row, 게이지명, 상태, 대여자, 대여일시, 로그사용자, 로그작업
    """
    items = list(changes)
    if not items:
        raise ValueError("처리할 게이지가 없습니다.")
    rows_seen: set[int] = set()
    requests = []
    log_rows = []
    for item in items:
        row_number = int(item["sheet_row"])
        if row_number < 2 or row_number in rows_seen:
            raise ValueError("유효하지 않거나 중복된 게이지 행입니다.")
        rows_seen.add(row_number)
        requests.append(
            {
                "updateCells": {
                    "range": {
                        "sheetId": int(status_sheet_id),
                        "startRowIndex": row_number - 1,
                        "endRowIndex": row_number,
                        "startColumnIndex": 1,
                        "endColumnIndex": 4,
                    },
                    "rows": [
                        {
                            "values": [
                                _text_cell(item["상태"]),
                                _text_cell(item["대여자"]),
                                _text_cell(item["대여일시"]),
                            ]
                        }
                    ],
                    "fields": "userEnteredValue",
                }
            }
        )
        log_rows.append(
            {
                "values": [
                    _text_cell(item["로그일시"]),
                    _text_cell(item["게이지명"]),
                    _text_cell(item["로그사용자"]),
                    _text_cell(item["로그작업"]),
                ]
            }
        )
    requests.append(
        {
            "appendCells": {
                "sheetId": int(logs_sheet_id),
                "rows": log_rows,
                "fields": "userEnteredValue",
            }
        }
    )
    return {"requests": requests, "includeSpreadsheetInResponse": False}


def update_local_records(records: list[dict], changes: Iterable[dict]) -> list[dict]:
    """API 성공 뒤 화면에 새 상태를 즉시 반영. 입력 records는 변경하지 않는다."""
    changed = {item["sheet_row"]: item for item in changes}
    result = []
    for record in records:
        new_record = dict(record)
        if record["sheet_row"] in changed:
            item = changed[record["sheet_row"]]
            for key in ("상태", "대여자", "대여일시"):
                new_record[key] = item[key]
        result.append(new_record)
    return result
