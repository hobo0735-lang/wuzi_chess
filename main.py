import sys
import json
from algorithm.engine_wrapper import RapfiEngine
from algorithm.ccgc_rules import CCGCRuleHandler
from algorithm.time_manager import TimeManager
from botbattle.adapter import BotBattleAdapter

def main():
    # 初始化核心组件
    engine = RapfiEngine(engine_path="bin/rapfi", model_path="bin/model.onnx")
    rule_handler = CCGCRuleHandler(engine)
    time_manager = TimeManager(total_budget_sec=900.0)
    adapter = BotBattleAdapter(rule_handler, time_manager)

    try:
        # 持续读取 stdin JSON 事件
        for line in sys.stdin:
            line_str = line.strip()
            if not line_str:
                continue

            event = json.loads(line_str)
            response = adapter.process_event(event)

            # 当需要做出落子/决策响应时，向 stdout 输出格式化 JSON
            if response is not None:
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()

    except Exception as e:
        sys.stderr.write(f"Fatal Engine Exception: {str(e)}\n")
        sys.stderr.flush()
        sys.exit(1)
    finally:
        engine.terminate()

if __name__ == "__main__":
    main()