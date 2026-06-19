import datetime
import json
import os
import random
import uuid

from .models import NotificationRecord, NotificationType, NotificationStatus
from .config import (
    NOTIFICATION_DB_FILE,
    NOTIFICATION_DELIVERY_SUCCESS_RATE,
    DEFAULT_APPROVERS,
    NOTIFICATION_ROLES_ON_ROLLBACK,
    ApprovalRole,
)


class NotificationManager:
    def __init__(self, compliance_logger=None):
        self._records: list[NotificationRecord] = []
        self._compliance_logger = compliance_logger
        self._load()

    def send_notification(
        self,
        release_id: str,
        notification_type: NotificationType,
        recipient_role: str,
        recipient_name: str = "",
        content_summary: str = "",
        drill_id: str = "",
    ) -> NotificationRecord:
        record = NotificationRecord(
            id=str(uuid.uuid4())[:8],
            release_id=release_id,
            drill_id=drill_id,
            notification_type=notification_type,
            recipient_role=recipient_role,
            recipient_name=recipient_name,
            content_summary=content_summary,
            sent_at=datetime.datetime.now(),
        )

        success = random.random() < NOTIFICATION_DELIVERY_SUCCESS_RATE
        if success:
            record.status = NotificationStatus.SENT
            record.delivery_result = "成功"
        else:
            record.status = NotificationStatus.SEND_FAILED
            record.delivery_result = "网络超时或接收方离线"

        self._records.append(record)
        self._save()

        if self._compliance_logger:
            self._compliance_logger.log(
                operation="通知发送",
                operator="NotificationManager",
                details=(
                    f"通知 {record.id} 发送给 {recipient_role} {recipient_name}, "
                    f"类型: {notification_type.value}, 结果: {record.delivery_result}"
                ),
                release_id=release_id,
            )

        return record

    def send_batch(
        self,
        release_id: str,
        notification_type: NotificationType,
        roles: list,
        content_summary: str = "",
        drill_id: str = "",
    ) -> list:
        records = []
        for role in roles:
            if isinstance(role, ApprovalRole):
                role_name = role.value
                recipient_name = DEFAULT_APPROVERS.get(role, "")
            else:
                role_name = role
                if role == "核心企业对接人":
                    recipient_name = "核心企业对接专员"
                else:
                    matched_role = None
                    for ar in ApprovalRole:
                        if ar.value == role:
                            matched_role = ar
                            break
                    if matched_role:
                        recipient_name = DEFAULT_APPROVERS.get(matched_role, "")
                    else:
                        recipient_name = ""

            record = self.send_notification(
                release_id=release_id,
                notification_type=notification_type,
                recipient_role=role_name,
                recipient_name=recipient_name,
                content_summary=content_summary,
                drill_id=drill_id,
            )
            records.append(record)
        return records

    def query(
        self,
        release_id: str = "",
        drill_id: str = "",
        notification_type: str = "",
        status: str = "",
    ) -> list:
        results = list(self._records)
        if release_id:
            results = [r for r in results if r.release_id == release_id]
        if drill_id:
            results = [r for r in results if r.drill_id == drill_id]
        if notification_type:
            results = [r for r in results if r.notification_type.value == notification_type]
        if status:
            results = [r for r in results if r.status.value == status]
        return results

    def get_by_release(self, release_id: str) -> list:
        return self.query(release_id=release_id)

    def _save(self):
        dir_path = os.path.dirname(NOTIFICATION_DB_FILE)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)
        data = []
        for record in self._records:
            data.append({
                "id": record.id,
                "release_id": record.release_id,
                "drill_id": record.drill_id,
                "notification_type": record.notification_type.value,
                "recipient_role": record.recipient_role,
                "recipient_name": record.recipient_name,
                "status": record.status.value,
                "content_summary": record.content_summary,
                "sent_at": record.sent_at.isoformat() if record.sent_at else "",
                "delivery_result": record.delivery_result,
            })
        with open(NOTIFICATION_DB_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load(self):
        if not os.path.exists(NOTIFICATION_DB_FILE):
            self._records = []
            return
        try:
            with open(NOTIFICATION_DB_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"[警告] 加载通知记录失败: {e}")
            self._records = []
            return
        self._records = []
        type_map = {t.value: t for t in NotificationType}
        status_map = {s.value: s for s in NotificationStatus}
        for item in data:
            try:
                sent_at = item.get("sent_at", "")
                if isinstance(sent_at, str) and sent_at:
                    try:
                        sent_at = datetime.datetime.fromisoformat(sent_at)
                    except (ValueError, TypeError):
                        sent_at = None
                else:
                    sent_at = None
                self._records.append(NotificationRecord(
                    id=item.get("id", ""),
                    release_id=item.get("release_id", ""),
                    drill_id=item.get("drill_id", ""),
                    notification_type=type_map.get(
                        item.get("notification_type", ""),
                        NotificationType.AUTO_ROLLBACK,
                    ),
                    recipient_role=item.get("recipient_role", ""),
                    recipient_name=item.get("recipient_name", ""),
                    status=status_map.get(
                        item.get("status", ""),
                        NotificationStatus.SENT,
                    ),
                    content_summary=item.get("content_summary", ""),
                    sent_at=sent_at,
                    delivery_result=item.get("delivery_result", "成功"),
                ))
            except Exception as e:
                print(f"[警告] 跳过通知记录 {item.get('id', '?')}: {e}")
                continue
