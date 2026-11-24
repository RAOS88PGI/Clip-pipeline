#!/usr/bin/env python3
"""Pemandu interaktif: cukup jawab pertanyaan, tidak perlu hafal perintah.
Jalankan:  python mulai.py
"""
import clip_pipeline


def tanya(pertanyaan, default=None):
    suffix = f" [{default}]" if default else ""
    jawab = input(f"{pertanyaan}{suffix}: ").strip()
    return jawab or default


def ya(pertanyaan, default="y"):
    return (tanya(pertanyaan + " (y/n)", default) or "").lower().startswith("y")


def kumpulkan_perintah():
    print("\n=== Pembuat Klip Video (yt-dlp + Whisper + FFmpeg) ===\n")
    url = tanya("1) Tempel link video YouTube")
    if not url:
        raise SystemExit("Link kosong, dibatalkan.")
    bahasa = tanya("2) Bahasa di video? (id = Indonesia, en = Inggris, kosong = deteksi otomatis)", "")
    print("\n3) Cara memilih klip:")
    print("   a = otomatis (komputer pilih potongan 30-60 detik)")
    print("   b = saya tentukan sendiri waktunya")
    mode = tanya("   Pilih a atau b", "a").lower()

    args = ["run", url]
    if bahasa:
        args += ["--lang", bahasa]
    if mode == "b":
        waktu = tanya('   Tulis waktu mulai-selesai, pisah koma. Contoh: 01:10-01:55,05:00-05:40')
        args += ["--clips", waktu]
    else:
        batas = tanya("   Maksimal berapa klip?", "5")
        args += ["--auto", "--limit", batas]
        kata = tanya("   Kata kunci (opsional, pisah koma, kosong = semua)", "")
        if kata:
            args += ["--keywords", kata]
    if ya("4) Ubah ke format vertikal 9:16 (Reels/TikTok/Shorts)?"):
        args.append("--vertical")
    if ya("5) Tempel subtitle ke video?"):
        args.append("--burn-subs")
    return args


if __name__ == "__main__":
    args = kumpulkan_perintah()
    print("\nMemulai... (video panjang bisa makan waktu beberapa menit)\n")
    clip_pipeline.main(args)
