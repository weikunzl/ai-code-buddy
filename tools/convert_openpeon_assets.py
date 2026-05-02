#!/usr/bin/env python3
import argparse
import pathlib
import struct
import wave


ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT_CPP = ROOT / "src" / "wav_assets.cpp"


def load_pcm16_mono(src_path: pathlib.Path, dst_rate: int = 11025, max_samples: int | None = 4096) -> list[int]:
    with wave.open(str(src_path), "rb") as wav:
        channels = wav.getnchannels()
        width = wav.getsampwidth()
        rate = wav.getframerate()
        frames = wav.readframes(wav.getnframes())

    if width != 2:
        raise ValueError(f"{src_path} expected 16-bit source, got width={width}")
    samples = [sample[0] for sample in struct.iter_unpack("<h", frames)]
    if channels == 2:
        mono = []
        for idx in range(0, len(samples), 2):
            mono.append((samples[idx] + samples[idx + 1]) // 2)
        samples = mono
    elif channels != 1:
        raise ValueError(f"{src_path} unsupported channels={channels}")
    if rate == dst_rate:
        pass
    elif rate % dst_rate == 0:
        step = rate // dst_rate
        down = []
        for idx in range(0, len(samples) - step + 1, step):
            window = samples[idx:idx + step]
            down.append(sum(window) // len(window))
        samples = down
    else:
        raise ValueError(f"{src_path} unsupported sample rate conversion {rate} -> {dst_rate}")
    samples = trim_silence(samples)
    if max_samples is not None and len(samples) > max_samples:
      samples = samples[:max_samples]
    return samples


def trim_silence(samples: list[int], threshold: int = 96, pad: int = 96) -> list[int]:
    if not samples:
        return samples
    start = 0
    end = len(samples)
    while start < end and abs(samples[start]) <= threshold:
        start += 1
    while end > start and abs(samples[end - 1]) <= threshold:
        end -= 1
    start = max(0, start - pad)
    end = min(len(samples), end + pad)
    return samples[start:end]


def format_array(name: str, samples: list[int], rate: int) -> str:
    lines = []
    for idx in range(0, len(samples), 12):
        chunk = ", ".join(f"{value:6d}" for value in samples[idx:idx + 12])
        lines.append(f"  {chunk},")
    body = "\n".join(lines)
    return (
        f"const int16_t {name}[] = {{\n{body}\n}};\n"
        f"const size_t {name}Samples = sizeof({name}) / sizeof({name}[0]);\n"
        f"const uint32_t {name}SampleRate = {rate};\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-required", required=True)
    parser.add_argument("--ui-click", required=True)
    parser.add_argument("--answer-sent", required=True)
    parser.add_argument("--complete", required=True)
    parser.add_argument("--rate", type=int, default=11025)
    parser.add_argument("--max-samples", type=int, default=4096)
    args = parser.parse_args()

    input_samples = load_pcm16_mono(pathlib.Path(args.input_required), args.rate, args.max_samples)
    ui_click_samples = load_pcm16_mono(pathlib.Path(args.ui_click), args.rate, args.max_samples)
    answer_samples = load_pcm16_mono(pathlib.Path(args.answer_sent), args.rate, args.max_samples)
    complete_samples = load_pcm16_mono(pathlib.Path(args.complete), args.rate, args.max_samples)

    out = (
        '#include "wav_assets.h"\n\n'
        + format_array("kInputRequiredPcm", input_samples, args.rate)
        + "\n"
        + format_array("kUiClickPcm", ui_click_samples, args.rate)
        + "\n"
        + format_array("kAnswerSentPcm", answer_samples, args.rate)
        + "\n"
        + format_array("kCompletePcm", complete_samples, args.rate)
    )
    OUT_CPP.write_text(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
