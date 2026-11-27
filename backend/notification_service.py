
import logging
from backend.database import get_connection

logger = logging.getLogger(__name__)


def log_notification(
    quote_id,
    recipient,
    notification_type,
    subject,
    message,
    status="sent"
):
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO notifications (
                        quote_id,
                        recipient,
                        notification_type,
                        subject,
                        message,
                        status
                    )
                    VALUES (%s, %s, %s, %s, %s, %s);
                    """,
                    (
                        quote_id,
                        recipient,
                        notification_type,
                        subject,
                        message,
                        status
                    )
                )

    except Exception:
        logger.exception("Could not save notification history")
