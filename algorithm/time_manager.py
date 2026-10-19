import os


class TimeManager:
    """Calculate a bounded per-turn budget from BotArena's side clock."""

    def __init__(
        self,
        total_budget_sec: float | None = None,
        safety_margin_sec: float = 10.0,
    ):
        self.total_budget = total_budget_sec or float(
            os.getenv("BOTARENA_TOTAL_TIME_SEC", "900")
        )
        self.safety_margin = safety_margin_sec
        self.estimated_moves_left = 30  # 五子棋中盘平均剩余有效棋步估算

    def calculate_time_limit_ms(self, remaining_sec: float, current_move_index: int) -> int:
        """
        计算当前步可调用的毫秒级时间预算
        """
        usable_time = max(0.0, remaining_sec - self.safety_margin)

        # 随步数增加，动态缩小预估剩余步数，防止死存时间
        est_left = max(10, self.estimated_moves_left - (current_move_index // 2))

        # 基础平摊时间
        allocated_sec = usable_time / est_left

        # 关键中盘阶段 (6~20手) 给予 1.5x 时间加权
        if 6 <= current_move_index <= 20:
            allocated_sec *= 1.5

        # Keep the local engine below its default 6000 ms turn setting and
        # leave time for JSON/process overhead.
        allocated_ms = int(allocated_sec * 1000)
        return max(100, min(5500, allocated_ms))
