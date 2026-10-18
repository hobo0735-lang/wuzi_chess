# algorithm/ccgc_rules.py

from typing import List, Dict, Any, Tuple


class CCGCRuleHandler:
    def __init__(self, engine):
        """
        CCGC (五手两打) 规则决策处理器
        :param engine: RapfiEngine 实例，提供局势评估与候选点预测接口
        """
        self.engine = engine
        # 三手交换阈值：若评估黑棋胜率超过该值，执行 Swap 拿黑棋
        self.swap_threshold = 0.52

    def handle_opening_proposal(self) -> Dict[str, Any]:
        """
        处理 phase: opening_proposal (开局提议)
        输出标准平衡开局（如瑞星局 S11）
        """
        return {
            "n": 2,
            "opening_code": "S11",
            "opening_name": "瑞星",
            "black1": {"x": 7, "y": 7},
            "white2": {"x": 7, "y": 8},
            "black3": {"x": 7, "y": 5}
        }

    def handle_swap_choice(self, opening_moves: List[Tuple[int, int]]) -> bool:
        """
        处理 phase: swap_choice (三手交换)
        评估前三手形成的盘面，决定是否选择三手交换
        :param opening_moves: 开局前三手坐标列表 [(x1, y1), (x2, y2), (x3, y3)]
        :return: True (交换，拿黑棋); False (不交换，保留白棋)
        """
        # 评估前三手盘面下黑棋的胜率
        black_win_rate = self.engine.evaluate_position(opening_moves, eval_player="black")
        return black_win_rate >= self.swap_threshold

    def handle_black5_candidates(
            self, current_moves: List[Tuple[int, int]], time_limit_ms: int
    ) -> List[Dict[str, int]]:
        """
        处理 phase: black5_candidates (执黑提供两个打点候选)
        调用引擎 Policy 网络获取得分最高的 2 个独立打点
        :param current_moves: 前四手历史记录 [(x1, y1), ..., (x4, y4)]
        :param time_limit_ms: 搜索用时预算 (毫秒)
        :return: 两个打点坐标列表 [{"x": x1, "y": y1}, {"x": x2, "y": y2}]
        """
        # 向引擎索取概率最高的前 N 个落子坐标
        candidates = self.engine.get_top_n_moves(
            moves_history=current_moves,
            top_n=2,
            time_limit_ms=time_limit_ms
        )

        # 兜底逻辑：若引擎输出不满足 2 个点，补齐任意合法空位
        if len(candidates) < 2:
            candidates = self._fill_fallback_candidates(current_moves, candidates)

        return [{"x": pt[0], "y": pt[1]} for pt in candidates[:2]]

    def handle_black5_select(
            self,
            current_moves: List[Tuple[int, int]],
            candidates: List[Dict[str, int]],
            time_limit_ms: int
    ) -> Dict[str, Any]:
        """
        处理 phase: black5_select (执白保留打点选择)
        分别模拟黑落子于打点 A 和 B，对比胜率，选择白棋胜率更高的打点
        :param current_moves: 前四手历史记录
        :param candidates: 黑方提交的两个候选点 [{"x": x1, "y": y1}, {"x": x2, "y": y2}]
        :param time_limit_ms: 评估用时预算 (毫秒)
        :return: 所选打点的数据结构 {"index": int, "point": {"x": int, "y": int}}
        """
        best_index = 0
        max_white_winrate = -1.0
        single_eval_time = max(50, time_limit_ms // len(candidates))

        for idx, cand in enumerate(candidates):
            test_move = (cand["x"], cand["y"])
            simulated_board = current_moves + [test_move]

            # 评估黑第 5 手落子后的胜率，推算白棋胜率
            black_winrate = self.engine.evaluate_position(
                simulated_board,
                eval_player="black",
                time_limit_ms=single_eval_time
            )
            white_winrate = 1.0 - black_winrate

            if white_winrate > max_white_winrate:
                max_white_winrate = white_winrate
                best_index = idx

        return {
            "index": best_index,
            "point": candidates[best_index]
        }

    def _fill_fallback_candidates(
            self, current_moves: List[Tuple[int, int]], existing_candidates: List[Tuple[int, int]]
    ) -> List[Tuple[int, int]]:
        """合法空位补充兜底"""
        occupied = set(current_moves) | set(existing_candidates)
        result = list(existing_candidates)
        for x in range(15):
            for y in range(15):
                if (x, y) not in occupied:
                    result.append((x, y))
                    if len(result) >= 2:
                        return result
        return result