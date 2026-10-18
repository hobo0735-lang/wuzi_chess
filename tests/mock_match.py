import json
import subprocess
import sys


def run_mock_test(log_filepath: str):
    """
    加载真实 JSON 比赛日志，模拟 BotBattle 平台逐行喂入 main.py 验证响应
    """
    with open(log_filepath, "r", encoding="utf-8") as f:
        log_data = json.load(f)

    events = log_data["replay"]["events"]

    # 启动 main.py 子进程
    proc = subprocess.Popen(
        [sys.executable, "main.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )

    print(f"--- 开始 Mock 测试: {log_filepath} ---")
    for idx, event in enumerate(events):
        event_str = json.dumps(event)
        proc.stdin.write(event_str + "\n")
        proc.stdin.flush()

        # 当事件为 turn 且轮到 Bot 行棋时，断言输出有效 JSON
        if event.get("type") == "turn":
            out_line = proc.stdout.readline()
            if out_line:
                response = json.loads(out_line)
                print(f"[Event {idx}] Phase: {event.get('phase')} -> Output: {response}")
            else:
                err = proc.stderr.read()
                print(f"[Error at Event {idx}]: {err}")
                break

    proc.terminate()
    print("--- Mock 测试完成 ---")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        run_mock_test(sys.argv[1])
    else:
        print("用法: python tests/mock_match.py <path_to_match_log.json>")