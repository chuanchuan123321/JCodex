"""Time utility tools"""
from datetime import datetime


class TimeTool:
    """Time-related utilities"""

    @staticmethod
    def get_current_time():
        """Get current time in formatted string"""
        now = datetime.now()
        # Format: "2026-02-06 19:45 (Friday)"
        day_name = now.strftime("%A")
        formatted_time = now.strftime("%Y-%m-%d %H:%M")
        return f"{formatted_time} ({day_name})"
