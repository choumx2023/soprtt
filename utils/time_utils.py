# utils/time_utils.py

from datetime import datetime, timezone, timedelta


UTC8 = timezone(timedelta(hours=8))


def epoch_to_utc8(epoch_time: float) -> str:
    """
    Convert Unix epoch to UTC+8 formatted string.
    """
    utc_time = datetime.fromtimestamp(epoch_time, tz=timezone.utc)
    return utc_time.astimezone(UTC8).strftime("%Y-%m-%d %H:%M:%S")


def epoch_to_utc8_ms(epoch_time: float) -> str:
    """
    Convert Unix epoch to UTC+8 with milliseconds.
    """
    utc_time = datetime.fromtimestamp(epoch_time, tz=timezone.utc)
    dt = utc_time.astimezone(UTC8)
    return dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]