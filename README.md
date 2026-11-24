# Clip Pipeline

Ubah video YouTube panjang jadi klip pendek, otomatis. Kamu cukup tempel link dan jawab beberapa pertanyaan.

## Mulai cepat (untuk pemula)
1. **Pasang sekali saja:** Python (python.org) dan FFmpeg. Windows: buka PowerShell, ketik `winget install ffmpeg`.
2. Di folder ini ketik: `pip install -r requirements.txt`
3. Setiap kali mau bikin klip, ketik: **`python mulai.py`** lalu jawab pertanyaannya. Hasil klip ada di folder `output/clips`.

## Pakai di chat Claude yang lain
Bilang saja ke Claude: *"Pakai repo clip-pipeline di GitHub saya. Pilihkan klip terbaik dari transkrip ini, lalu beri perintahnya."* Atau tempel isi file `output/ID.transcript.txt` dan minta Claude menentukan waktu klipnya.

---

## Penjelasan teknis (boleh dilewati)
Tiga alat yang dipakai:

| Langkah | Alat | Fungsi |
|---|---|---|
| 1 | **yt-dlp** | unduh video |
| 2 | **Whisper** | bikin teks (transkrip + subtitle) |
| 3 | **FFmpeg** | potong klip |

## Instalasi (sekali saja)
1. Pasang **Python 3.9+** dan **FFmpeg** (Windows: `winget install ffmpeg`, Mac: `brew install ffmpeg`).
2. Di folder ini jalankan: `pip install -r requirements.txt`

## Cara pakai
**Paling gampang** (unduh, transkrip, potong otomatis jadi klip 30-60 detik, format 9:16 + subtitle):
```
python clip_pipeline.py run "https://youtube.com/watch?v=XXXX" --auto --vertical --burn-subs
```
Hasil ada di `output/clips/`.

**Pilih potongan sendiri** (waktu `mulai-selesai`, dipisah koma):
```
python clip_pipeline.py run "URL" --clips "00:01:10-00:01:55,05:00-05:40"
```

**Langkah terpisah** (berguna untuk video panjang):
```
python clip_pipeline.py download "URL"
python clip_pipeline.py transcribe output/ID.mp4 --lang id
python clip_pipeline.py clip output/ID.mp4 --auto --keywords "bitcoin,rug pull" --limit 5 --vertical
```

## Tips
- Setelah `transcribe`, buka `output/ID.transcript.txt`. Tempel isinya ke Claude dan minta "pilih 5 bagian paling menarik beserta waktunya", lalu pakai hasilnya di `--clips`.
- Model Whisper: `tiny` cepat tapi kurang akurat, `small` seimbang (default), `medium`/`large` paling akurat tapi lambat (idealnya pakai GPU).
- Bahasa Indonesia: tambahkan `--lang id`.
- Hanya unduh video yang kamu punya haknya atau yang lisensinya mengizinkan dipakai ulang.
