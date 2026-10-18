import json
from typing import Dict, Any, Optional, Tuple, List
from algorithm.ccgc_rules import CCGCRuleHandler
from algorithm.time_manager import TimeManager

class BotBattleAdapter:
    """负责平台 JSON 协议的解析、状态更新与决策路由"""

    def __init__(self, rule_handler: CCGCRuleHandler, time_manager: TimeManager):
        self.rule_handler = rule_handler
        self.time_manager = time_manager
        self.my_seat: Optional[int] = None
        self.my_color: Optional[int] = None  # 0: 黑, 1: 白
        self.moves_history: List[Tuple[int, int]] = []
        self.current_remaining_time: float = 900.0

    def process_event(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        event_type = event.get("type")

        if event_type == "match_start":
            self.moves_history.clear()
            return None

        elif event_type == "time_used":
            # 记录自身剩余时间
            if event.get("seat") == self.my_seat:
                self.current_remaining_time = event.get("remaining", 900.0)
            return None

        elif event_type == "opening":
            # 同步开局三手
            b1, w2, b3 = event["black1"], event["white2"], event["black3"]
            self.moves_history.extend([(b1["x"], b1["y"]), (w2["x"], w2["y"]), (b3["x"], b3["y"])])
            return None

        elif event_type == "swap":
            # 三手交换后更新落子方色彩绑定
            seat_colors = event.get("seat_colors", [0, 1])
            if self.my_seat is not None:
                self.my_color = seat_colors[self.my_seat]
            return None

        elif event_type == "move":
            # 同步盘面常规落子
            self.moves_history.append((event["x"], event["y"]))
            return None

        elif event_type == "turn":
            # 确定己方 seat 标识
            if self.my_seat is None:
                self.my_seat = event.get("player")
                self.my_color = event.get("color")

            phase = event.get("phase")
            current_move_idx = len(self.moves_history) + 1
            time_limit = self.time_manager.calculate_time_limit_ms(
                self.current_remaining_time, current_move_idx
            )

            # 根据阶段路由至 CCGC 规则决策器
            if phase == "opening_proposal":
                return self.rule_handler.handle_opening_proposal()

            elif phase == "swap_choice":
                swapped = self.rule_handler.handle_swap_choice(self.moves_history[:3])
                return {"swapped": swapped}

            elif phase == "black5_candidates":
                candidates = self.rule_handler.handle_black5_candidates(
                    self.moves_history, time_limit
                )
                return {"n": len(candidates), "points": candidates}

            elif phase == "black5_select":
                # 假设平台在 turn 事件或上下文附带了 candidates
                candidates = event.get("candidates", [])
                return self.rule_handler.handle_black5_select(
                    self.moves_history, candidates, time_limit
                )

            elif phase == "normal_play":
                x, y = self.rule_handler.engine.search_best_move(
                    self.moves_history, time_limit
                )
                return {"x": x, "y": y}

        return None

