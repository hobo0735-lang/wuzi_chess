class TimeManager:
    """根据包干剩余用时动态计算单步思考上限"""

    def __init__(self, total_budget_sec: float = 900.0, safety_margin_sec: float = 10.0):
        self.total_budget = total_budget_sec
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

        # 约束在 [100ms, 15000ms] 范围内
        allocated_ms = int(allocated_sec * 1000)
        return max(100, min(15000, allocated_ms))