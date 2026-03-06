# main.py

import argparse
from core.engine import MLTEngine


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("pcap_file")
    parser.add_argument("--monitor", nargs="*", help="Monitor IPs")
    parser.add_argument("--target", nargs="*", help="Target IPs")

    args = parser.parse_args()

    engine = MLTEngine(
        monitor_ips=args.monitor,
        target_ips=args.target
    )
    engine.run(args.pcap_file)