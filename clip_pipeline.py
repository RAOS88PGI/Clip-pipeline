#!/usr/bin/env python3
"""
Clip Pipeline: yt-dlp (unduh video) -> Whisper (bikin teks) -> FFmpeg (potong klip)

Contoh paling gampang (satu perintah):
    python clip_pipeline.py run "https://youtube.com/watch?v=XXXX" --auto --vertical

Perintah terpisah:
    python clip_pipeline.py download "URL"
    python clip_pipeline.py transcribe output/video.mp4
    python clip_pipeline.py clip output/video.mp4 --clips "00:01:10-00:01:55,00:05:00-00:05:40"
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


# ---------- util ----------
def need(binary):
    if not shutil.which(binary):
        sys.exit(f"[ERROR] '{binary}' belum terpasang. Lihat README.md bagian Instalasi.")


def fmt_ts(sec, srt=False):
    ms = int(round((sec - int(sec)) * 1000))
    s = int(sec)
    h, m, s = s // 3600, (s % 3600) // 60, s % 60
    sep = "," if srt else "."
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"


def parse_ts(text):
    """'90' | '1:30' | '00:01:30' | '00:01:30.5' -> detik (float)"""
    parts = text.strip().split(":")
    if not 1 <= len(parts) <= 3:
        raise ValueError(f"Format waktu salah: {text!r}")
    total = 0.0
    for p in parts:
        total = total * 60 + float(p)
    return total


def parse_clips(spec):
    clips = []
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" not in chunk:
            raise ValueError(f"Klip harus 'mulai-selesai', dapat: {chunk!r}")
        a, b = chunk.split("-", 1)
        start, end = parse_ts(a), parse_ts(b)
        if end <= start:
            raise ValueError(f"Waktu selesai harus > mulai: {chunk!r}")
        clips.append((start, end))
    return clips


# ---------- 1. yt-dlp ----------
def download(url, outdir):
    need("yt-dlp")
    outdir.mkdir(parents=True, exist_ok=True)
    template = str(outdir / "%(id)s.%(ext)s")
    cmd = [
        "yt-dlp",
        "-f", "bv*[height<=1080]+ba/b[height<=1080]/b",
        "--merge-output-format", "mp4",
        "--no-playlist",
        "-o", template,
        "--print", "after_move:filepath",
        url,
    ]
    print("[1/3] Mengunduh video...")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        sys.exit("[ERROR] yt-dlp gagal:\n" + res.stderr[-1500:])
    path = Path(res.stdout.strip().splitlines()[-1])
    print(f"      selesai: {path}")
    return path


# ---------- 2. Whisper ----------
def transcribe(video, model_name="small", language=None):
    try:
        import whisper  # pip install openai-whisper
    except ImportError:
        sys.exit("[ERROR] Whisper belum terpasang. Jalankan: pip install openai-whisper")
    need("ffmpeg")
    video = Path(video)
    print(f"[2/3] Membuat teks dengan Whisper (model: {model_name})... bisa lama untuk video panjang")
    model = whisper.load_model(model_name)
    result = model.transcribe(str(video), language=language, verbose=False)
    segments = [
        {"start": s["start"], "end": s["end"], "text": s["text"].strip()}
        for s in result["segments"]
    ]
    base = video.with_suffix("")
    Path(f"{base}.transcript.json").write_text(
        json.dumps({"language": result.get("language"), "segments": segments},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    write_srt(segments, Path(f"{base}.srt"))
    Path(f"{base}.transcript.txt").write_text(
        "\n".join(f"[{fmt_ts(s['start'])[:8]}] {s['text']}" for s in segments),
        encoding="utf-8")
    print(f"      selesai: {base}.srt, .transcript.txt, .transcript.json")
    return segments


def write_srt(segments, path, offset=0.0):
    lines = []
    for i, s in enumerate(segments, 1):
        lines += [str(i),
                  f"{fmt_ts(max(0, s['start'] - offset), True)} --> {fmt_ts(max(0, s['end'] - offset), True)}",
                  s["text"], ""]
    Path(path).write_text("\n".join(lines), encoding="utf-8")


# ---------- pilih klip otomatis ----------
def auto_clips(segments, min_len=30, max_len=60, keywords=None, limit=None):
    """Gabungkan segmen berurutan jadi klip berdurasi min_len..max_len,
    selalu berhenti di akhir kalimat/segmen supaya tidak terpotong di tengah kata.
    Jika keywords diberikan, hanya klip yang mengandung kata itu yang dipakai."""
    clips, cur_start, cur_end, cur_text = [], None, None, []
    for s in segments:
        if cur_start is None:
            cur_start = s["start"]
        cur_end = s["end"]
        cur_text.append(s["text"])
        dur = cur_end - cur_start
        ends_sentence = s["text"].rstrip().endswith((".", "?", "!"))
        if dur >= max_len or (dur >= min_len and ends_sentence):
            clips.append((cur_start, cur_end, " ".join(cur_text)))
            cur_start, cur_end, cur_text = None, None, []
    if cur_start is not None and cur_end - cur_start >= min_len / 2:
        clips.append((cur_start, cur_end, " ".join(cur_text)))
    if keywords:
        kws = [k.lower() for k in keywords]
        clips = [c for c in clips if any(k in c[2].lower() for k in kws)]
    if limit:
        clips = clips[:limit]
    return [(a, b) for a, b, _ in clips]


# ---------- 3. FFmpeg ----------
def cut_clips(video, clips, outdir, segments=None, vertical=False, burn_subs=False, pad=0.3):
    need("ffmpeg")
    video, outdir = Path(video), Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    print(f"[3/3] Memotong {len(clips)} klip dengan FFmpeg...")
    made = []
    for i, (start, end) in enumerate(clips, 1):
        start = max(0, start - pad)
        end = end + pad
        out = outdir / f"{video.stem}_klip{i:02d}.mp4"
        vf = []
        if vertical:  # crop tengah ke 9:16 lalu 1080x1920
            vf.append("crop=ih*9/16:ih,scale=1080:1920")
        srt_path = None
        if burn_subs and segments:
            clip_segs = [s for s in segments if s["end"] > start and s["start"] < end]
            if clip_segs:
                srt_path = outdir / f"{out.stem}.srt"
                write_srt(clip_segs, srt_path, offset=start)
                style = "FontSize=14,Outline=2,MarginV=60,Alignment=2" if vertical else "FontSize=18,Outline=2"
                # path di filter ffmpeg: escape ':' dan '\' (penting untuk Windows)
                p = str(srt_path.resolve()).replace("\\", "/").replace(":", "\\:")
                vf.append(f"subtitles='{p}':force_style='{style}'")
        cmd = ["ffmpeg", "-y", "-loglevel", "error",
               "-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", str(video)]
        if vf:
            cmd += ["-vf", ",".join(vf)]
        cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out)]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            print(f"      [GAGAL] klip {i}: {res.stderr[-400:]}")
            continue
        made.append(out)
        print(f"      klip {i}: {fmt_ts(start)[:8]} -> {fmt_ts(end)[:8]}  =>  {out.name}")
    return made


# ---------- CLI ----------
def load_segments(video):
    p = Path(video).with_suffix("").as_posix() + ".transcript.json"
    if Path(p).exists():
        return json.loads(Path(p).read_text(encoding="utf-8"))["segments"]
    return None


def build_parser():
    ap = argparse.ArgumentParser(description="yt-dlp -> Whisper -> FFmpeg")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add_clip_opts(p):
        p.add_argument("--clips", help='Waktu manual, mis. "00:01:10-00:01:55,05:00-05:40"')
        p.add_argument("--auto", action="store_true", help="Pilih klip otomatis dari transkrip")
        p.add_argument("--min", type=float, default=30, help="Durasi klip minimum (detik, mode auto)")
        p.add_argument("--max", type=float, default=60, help="Durasi klip maksimum (detik, mode auto)")
        p.add_argument("--keywords", help="Kata kunci dipisah koma (mode auto): hanya bagian yang memuat kata ini")
        p.add_argument("--limit", type=int, help="Batas jumlah klip (mode auto)")
        p.add_argument("--vertical", action="store_true", help="Ubah ke 9:16 (Reels/TikTok/Shorts)")
        p.add_argument("--burn-subs", action="store_true", help="Tempel subtitle ke video")

    d = sub.add_parser("download", help="Unduh video (yt-dlp)")
    d.add_argument("url")
    d.add_argument("--out", default="output")

    t = sub.add_parser("transcribe", help="Buat teks (Whisper)")
    t.add_argument("video")
    t.add_argument("--model", default="small", help="tiny/base/small/medium/large")
    t.add_argument("--lang", help="Kode bahasa, mis. id atau en (default: deteksi otomatis)")

    c = sub.add_parser("clip", help="Potong klip (FFmpeg)")
    c.add_argument("video")
    c.add_argument("--out", default="output/clips")
    add_clip_opts(c)

    r = sub.add_parser("run", help="Jalankan semua langkah sekaligus")
    r.add_argument("url")
    r.add_argument("--out", default="output")
    r.add_argument("--model", default="small")
    r.add_argument("--lang")
    add_clip_opts(r)
    return ap


def decide_clips(args, segments):
    if args.clips:
        return parse_clips(args.clips)
    if args.auto:
        if not segments:
            sys.exit("[ERROR] Mode --auto butuh transkrip. Jalankan 'transcribe' dulu.")
        kws = [k.strip() for k in args.keywords.split(",")] if args.keywords else None
        return auto_clips(segments, args.min, args.max, kws, args.limit)
    sys.exit("[ERROR] Pilih --clips \"mulai-selesai\" atau --auto")


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.cmd == "download":
        download(args.url, Path(args.out))
    elif args.cmd == "transcribe":
        transcribe(args.video, args.model, args.lang)
    elif args.cmd == "clip":
        segs = load_segments(args.video)
        clips = decide_clips(args, segs)
        cut_clips(args.video, clips, args.out, segs, args.vertical, args.burn_subs)
    elif args.cmd == "run":
        video = download(args.url, Path(args.out))
        segs = transcribe(video, args.model, args.lang)
        clips = decide_clips(args, segs)
        made = cut_clips(video, clips, Path(args.out) / "clips", segs, args.vertical, args.burn_subs)
        print(f"\nSelesai! {len(made)} klip ada di {Path(args.out) / 'clips'}")


if __name__ == "__main__":
    main()
