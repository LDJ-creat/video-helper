from __future__ import annotations

import argparse

from core.external.asr_faster_whisper import prefetch_faster_whisper_model


def main() -> None:
	p = argparse.ArgumentParser(description="Prefetch faster-whisper ASR model into DATA_DIR")
	p.add_argument("--model", default="base", help="Model size (tiny/base/small/medium/large-v3, etc)")
	args = p.parse_args()

	res = prefetch_faster_whisper_model(model_size=str(args.model))
	print(res)


if __name__ == "__main__":
	main()
