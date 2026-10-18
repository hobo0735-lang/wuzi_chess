import subprocess
import os
import select
import time
from typing import List, Tuple, Optional


class RapfiEngine:
    """通过 Pipe 管理 C++ Rapfi 进程的 CLI/GTP 通信包装类"""

    def __init__(self, engine_path: str = "bin/rapfi", model_path: str = "bin/model.onnx"):
        if not os.path.exists(engine_path):
            raise FileNotFoundError(f"Rapfi 可执行文件未找到: {engine_path}")

        cmd = [engine_path, "--model", model_path]
        self.process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )

    def send_command(self, cmd: str) -> List[str]:
        """向 Rapfi 发送指令并同步获取响应文本行"""
        if self.process.poll() is not None:
            raise RuntimeError("Rapfi 引擎进程已异常退出")

        self.process.stdin.write(cmd.strip() + "\n")
        self.process.stdin.flush()

        response = []
        while True:
            line = self.process.stdout.readline()
            if not line or line.strip() == "OK" or line.startswith("error"):
                if line and line.startswith("error"):
                    raise RuntimeError(f"Rapfi 执行报错: {line.strip()}")
                break
            response.append(line.strip())
        return response

    def sync_board(self, moves_history: List[Tuple[int, int]]):
        """重置并同步当前盘面历史落子"""
        self.send_command("boardsize 15")
        self.send_command("clear_board")
        for x, y in moves_history:
            self.send_command(f"play {x} {y}")

    def evaluate_position(
            self,
            moves_history: List[Tuple[int, int]],
            eval_player: str = "black",
            time_limit_ms: int = 100
    ) -> float:
        """
        评估当前盘面相对某方的胜率胜值 [0.0, 1.0]
        :return: 黑棋胜率 (0.0~1.0)
        """
        self.sync_board(moves_history)
        res = self.send_command(f"eval timeout {time_limit_ms}")
        # 假设 Rapfi 返回格式: winrate 0.5432
        for line in res:
            if "winrate" in line:
                val = float(line.split()[-1])
                return val if eval_player == "black" else 1.0 - val
        return 0.5

    def get_top_n_moves(
            self,
            moves_history: List[Tuple[int, int]],
            top_n: int = 2,
            time_limit_ms: int = 200
    ) -> List[Tuple[int, int]]:
        """调用 Policy / MCTS 根节点输出评分最高的 Top N 个落子坐标"""
        self.sync_board(moves_history)
        res = self.send_command(f"get_policy top {top_n} timeout {time_limit_ms}")
        # 假设 Rapfi 返回格式每行为: x y score
        candidates = []
        for line in res:
            parts = line.split()
            if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
                candidates.append((int(parts[0]), int(parts[1])))
        return candidates[:top_n]

    def search_best_move(
            self,
            moves_history: List[Tuple[int, int]],
            time_limit_ms: int
    ) -> Tuple[int, int]:
        """进行 MCTS 深算并输出最佳落子坐标"""
        self.sync_board(moves_history)
        res = self.send_command(f"genmove timeout {time_limit_ms}")
        # 假设 Rapfi 返回格式: move x y
        for line in res:
            parts = line.split()
            if len(parts) >= 3 and parts[0] == "move":
                return int(parts[1]), int(parts[2])
        raise RuntimeError("Rapfi 未能在时限内输出有效落子")

    def terminate(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            self.process.wait()