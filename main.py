# main.py

import argparse
import json
from core.engine import MLTEngine


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("pcap_file")
    parser.add_argument("--monitor", nargs="*", help="Monitor IPs")
    parser.add_argument("--target", nargs="*", help="Target IPs")
    parser.add_argument("--output_dir", default="outputs", help="Output directory")
    parser.add_argument("--log_events_json", default=None, help="Optional JSON file containing log events")

    args = parser.parse_args()

    log_events = None
    if args.log_events_json:
        with open(args.log_events_json, "r", encoding="utf-8") as f:
            log_events = json.load(f)

    engine = MLTEngine(
        monitor_ips=args.monitor,
        target_ips=args.target
    )

    result = engine.run(
        args.pcap_file,
        output_dir=args.output_dir,
        log_events=log_events,
    )

    print("\n===== Final Output =====")
    print(json.dumps(result, indent=4, ensure_ascii=False))